"""Opportunity ranking: eligibility, fit, competition evidence — separate.

- Eligibility: hard constraints from the career profile (exclusions, experience
  blockers, location/work-mode conflicts). Unknown requirements stay unknown.
- Fit: the existing career-fit engine against a JD. With no vacancy there is
  no JD, so fit is unknown — never guessed.
- Competition: observed applicant counts with source, timestamp and measurement
  meaning. Missing counts stay unknown; clicks are not applications; unlike
  platforms are never compared as equal measurements.
- Priority: weighted formula over available factors only, renormalized, with
  contributions, coverage and input hashes persisted per evaluation version.
"""

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.analysis.fit import FitConfig, _user_years, classify_job
from app.analysis.keywords import analyze_jd, extract_experience_years, tokenize

FORMULA_VERSION = "opportunity-priority-v1"
DEFAULT_WEIGHTS = {"fit": 0.70, "freshness": 0.20, "opportunity": 0.10}
FRESHNESS_MAX_AGE_DAYS = 90
PROXY_FIRST_SEEN_DAYS = 14

#: Meanings that count as completed/applicant measurements. Anything else
#: (clicks, views, "people who clicked apply") is recorded but not comparable.
COMPARABLE_MEANINGS = ("completed_applications", "applicants", "applicant_count", "applications")


@dataclass
class RankingWeights:
    fit: float = DEFAULT_WEIGHTS["fit"]
    freshness: float = DEFAULT_WEIGHTS["freshness"]
    opportunity: float = DEFAULT_WEIGHTS["opportunity"]

    def validate(self) -> None:
        vals = {"fit": self.fit, "freshness": self.freshness, "opportunity": self.opportunity}
        for name, v in vals.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"weight '{name}' must be a finite number")
            if v < 0:
                raise ValueError(f"weight '{name}' must not be negative")
        if sum(vals.values()) <= 0:
            raise ValueError("at least one ranking weight must be positive")

    def as_dict(self) -> dict:
        return {"fit": float(self.fit), "freshness": float(self.freshness),
                "opportunity": float(self.opportunity)}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(s: str) -> str:
    return " ".join(tokenize(s or ""))


def _blob(*parts: str) -> str:
    return _norm(" ".join(p for p in parts if p))[:4000]


def _age_days(at: datetime | None, now: datetime | None = None) -> float | None:
    if at is None:
        return None
    now = now or _now()
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return (now - at).total_seconds() / 86400.0


# ---- eligibility ---------------------------------------------------------


def _check_role_exclusion(kind: str, profile: dict, title: str, description: str,
                          company: str | None) -> dict:
    excluded = [e for e in (_norm(x) for x in (profile.get("excluded_roles") or [])) if e]
    if not excluded:
        return {"key": "role_exclusion", "status": "satisfied",
                "reason": "No role exclusions configured."}
    if kind == "startup_prospect":
        return {"key": "role_exclusion", "status": "unknown",
                "reason": "No vacancy listing — role exclusions cannot be checked."}
    blob = _blob(title, description, company or "")
    for exc in excluded:
        if exc and (exc in blob or blob in exc
                    or any(exc in t or t in exc for t in (title.lower(),))):
            return {"key": "role_exclusion", "status": "violated",
                    "reason": f"Matches your exclusion '{exc}'."}
    return {"key": "role_exclusion", "status": "satisfied",
            "reason": "Listing does not match any excluded role."}


def _check_experience(kind: str, profile: dict, description: str) -> dict:
    if kind == "startup_prospect":
        return {"key": "experience_requirement", "status": "unknown",
                "reason": "No vacancy listing — experience requirement cannot be established."}
    req = extract_experience_years(description or "")
    years = _user_years(profile)
    if req is None:
        return {"key": "experience_requirement", "status": "unknown",
                "reason": "Listing does not state an experience requirement."}
    if years is None:
        return {"key": "experience_requirement", "status": "unknown",
                "reason": "Your profile has no experience timeline to check against."}
    if req > years + 1 and req - years >= 5:
        return {"key": "experience_requirement", "status": "violated",
                "reason": f"Requires {req:g}+ years; your profile shows {years:g}."}
    return {"key": "experience_requirement", "status": "satisfied",
            "reason": f"Required {req:g} years vs profile {years:g} years."}


def _check_location(kind: str, profile: dict, jd_location: str | None,
                    org_location: str | None) -> dict:
    pref = str((profile.get("preferences", {}) or {}).get("location", "") or "").strip()
    if not pref:
        return {"key": "location_preference", "status": "satisfied",
                "reason": "No location preference configured."}
    loc = jd_location or org_location
    if not loc:
        what = "listing has no location" if kind == "vacancy" else "company location not established"
        return {"key": "location_preference", "status": "unknown",
                "reason": f"Location preference cannot be checked — {what}."}
    if pref.lower() not in loc.lower() and loc.lower() not in pref.lower():
        return {"key": "location_preference", "status": "violated",
                "reason": f"Location '{loc}' differs from your preference '{pref}'."}
    return {"key": "location_preference", "status": "satisfied",
            "reason": f"Location '{loc}' matches your preference."}


def _work_mode_signals(text: str) -> dict:
    t = (text or "").lower()
    return {
        "remote": "remote" in t,
        "hybrid": "hybrid" in t,
        "onsite": any(x in t for x in ("on-site", "onsite", "on site")),
    }


def _check_work_mode(kind: str, profile: dict, text: str,
                     location: str | None = None) -> dict:
    pref = (profile.get("preferences", {}) or {}).get("remote")
    if pref is None or pref == "":
        return {"key": "work_mode", "status": "satisfied",
                "reason": "No remote/hybrid/onsite preference configured."}
    wants_remote = pref is True or str(pref).lower() in ("remote", "only_remote")
    if kind == "startup_prospect":
        return {"key": "work_mode", "status": "unknown",
                "reason": "No vacancy listing — work mode cannot be established."}
    sig = _work_mode_signals(f"{text} {location or ''}")
    if not any(sig.values()):
        return {"key": "work_mode", "status": "unknown",
                "reason": "Listing does not state a work mode."}
    if wants_remote and sig["onsite"] and not sig["remote"] and not sig["hybrid"]:
        return {"key": "work_mode", "status": "violated",
                "reason": "Listing is on-site only; your preference is remote."}
    return {"key": "work_mode", "status": "satisfied",
            "reason": "Work mode is compatible with your preference."}


def evaluate_eligibility(kind: str, profile: dict, *, title: str | None = None,
                         description: str | None = None, company: str | None = None,
                         jd_location: str | None = None,
                         org_location: str | None = None) -> dict:
    checks = [
        _check_role_exclusion(kind, profile, title or "", description or "", company),
        _check_experience(kind, profile, description or ""),
        _check_location(kind, profile, jd_location, org_location),
        _check_work_mode(kind, profile, f"{title or ''} {description or ''}", jd_location),
    ]
    if any(c["status"] == "violated" for c in checks):
        status = "ineligible"
    elif any(c["status"] == "unknown" for c in checks):
        status = "unknown"
    else:
        status = "eligible"
    return {
        "status": status,
        "checks": checks,
        "reasons": [c["reason"] for c in checks if c["status"] != "satisfied"],
    }


# ---- fit -----------------------------------------------------------------


def _fit_from_jd(jd_text: str, title: str, location: str, profile: dict) -> dict:
    try:
        jd = analyze_jd(jd_text or "")
    except ValueError:
        return {"classification": "needs_review", "score": 0.0,
                "factors": {"direction": 0, "tech_edu": 0, "transfer": 0, "progression": 0},
                "reasons": [], "conflicts": [], "unknowns": ["Listing has no extractable description text."],
                "available": False, "reason": "Listing has no description text to evaluate fit against."}
    jd.update({"title": title or "", "location": location or "",
               "role_category": "", "description_excerpt": (jd_text or "")[:2000]})
    result = classify_job(jd, profile, FitConfig())
    available = result["classification"] != "needs_review"
    return {
        "classification": result["classification"], "score": result["score"],
        "factors": result["factors"], "reasons": result["reasons"],
        "conflicts": result["conflicts"], "unknowns": result.get("unknown", []),
        "available": available,
        "reason": None if available else "Fit verdict is needs_review — requirements could not be extracted.",
    }


def _fit_without_jd(profile: dict) -> dict:
    result = classify_job({"title": "", "role_category": "", "skills": [], "keywords": [],
                           "responsibilities": [], "description_excerpt": ""}, profile, FitConfig())
    return {
        "classification": result["classification"], "score": result["score"],
        "factors": result["factors"], "reasons": result["reasons"],
        "conflicts": result["conflicts"], "unknowns": result.get("unknown", []),
        "available": False,
        "reason": "No vacancy listing — fit against a JD is unknown, not poor.",
    }


# ---- competition --------------------------------------------------------


def summarize_competition(observations: list) -> dict:
    """Latest observation wins. Missing stays missing — never zero."""
    if not observations:
        return {"status": "missing", "observed_count": None, "comparable": False,
                "age_days": None, "observation_count": 0,
                "reason": "No applicant-count observation recorded. Missing counts stay "
                          "unknown — never treated as zero competition."}
    latest = observations[0]
    age = _age_days(latest.get("observed_at"))
    observed_at = latest.get("observed_at")
    return {
        "status": "observed",
        "observed_count": latest.get("observed_count"),
        "platform": latest.get("platform"),
        "source": latest.get("source"),
        "observed_at": observed_at.isoformat() if isinstance(observed_at, datetime) else observed_at,
        "meaning": latest.get("meaning", "unknown"),
        "comparable": bool(latest.get("comparable")),
        "age_days": round(age, 1) if age is not None else None,
        "note": latest.get("note"),
        "observation_count": len(observations),
    }


# ---- proxy signals (labeled, never counts) -------------------------------


def derive_signals(opp: dict, competition: dict) -> list[dict]:
    """Visibility proxies. Each is labeled a proxy — none is proof of fewer
    applicants, and first-seen date is never presented as posting date."""
    signals: list[dict] = []
    age = _age_days(opp.get("first_seen_at"))
    if age is not None and age <= PROXY_FIRST_SEEN_DAYS:
        signals.append({
            "signal": "first_seen_recent", "kind": "proxy",
            "evidence": f"First seen {int(age)} day(s) ago.",
            "caution": "First-seen date is not the posting date; recency is a proxy, "
                       "not a measured applicant count.",
        })
    if opp.get("kind") == "startup_prospect":
        signals.append({
            "signal": "no_public_listing", "kind": "proxy",
            "evidence": "No vacancy found in the checked sources for this company.",
            "caution": "Absence of evidence is not evidence the company is not hiring.",
        })
    ev = opp.get("source_evidence") or []
    if opp.get("kind") == "vacancy" and ev:
        doms = {e.get("domain") for e in ev if e.get("domain")}
        if len(doms) == 1:
            signals.append({
                "signal": "single_distribution_channel", "kind": "proxy",
                "evidence": f"All {len(ev)} source observation(s) come from one domain.",
                "caution": "Small distribution footprint is a proxy, not a measured applicant count.",
            })
    return signals


# ---- priority formula ------------------------------------------------------


def compute_priority(fit: dict, freshness_at: datetime | None, signals: list[dict],
                     weights: RankingWeights) -> dict:
    """70% fit + 20% freshness + 10% opportunity signal, each 0–100 when
    available. Unavailable factors are excluded and the rest renormalized."""
    factors: dict[str, dict] = {}
    if fit.get("available") and fit.get("score") is not None:
        factors["fit"] = {"available": True, "raw": round(fit["score"] * 100, 2)}
    else:
        factors["fit"] = {"available": False, "raw": None, "reason": fit.get("reason")}
    age = _age_days(freshness_at)
    if age is not None:
        factors["freshness"] = {"available": True, "raw": round(max(0.0, 100.0 * (1 - age / FRESHNESS_MAX_AGE_DAYS)), 2),
                                "basis": "first_seen"}
    else:
        factors["freshness"] = {"available": False, "raw": None,
                                "reason": "No first-seen or posting date recorded."}
    factors["opportunity"] = {
        "available": bool(signals),
        "raw": round(min(100.0, 25.0 * len(signals)), 2) if signals else None,
        "reason": None if signals else "No evidence-backed opportunity signals observed.",
    }

    wmap = weights.as_dict()
    available = [f for f in factors if factors[f]["available"]]
    total_w = sum(wmap[f] for f in available)
    contributions, excluded = [], []
    for name, f in factors.items():
        if f["available"]:
            eff = wmap[name] / total_w if total_w else 0.0
            contributions.append({
                "factor": name, "available": True, "weight": wmap[name],
                "effective_weight": round(eff, 4), "raw": f["raw"],
                "basis": f.get("basis"),
                "contribution": round(f["raw"] * eff, 2),
            })
        else:
            excluded.append({"factor": name, "reason": f.get("reason", "not available")})
    score = sum(c["contribution"] for c in contributions) if contributions else None
    return {
        "score": round(score, 2) if score is not None else None,
        "contributions": contributions,
        "coverage": {
            "available_factors": available,
            "excluded_factors": excluded,
            "formula": FORMULA_VERSION,
        },
    }


# ---- orchestration ---------------------------------------------------------


def _input_hashes(opp: dict, profile: dict) -> dict:
    identity = json.dumps({
        "job_id": opp.get("job_id"),
        "kind": opp.get("kind"),
        "title": opp.get("title"),
        "description": opp.get("description"),
    }, sort_keys=True, default=str)
    prof = json.dumps(profile, sort_keys=True, default=str)
    return {"listing": hashlib.sha256(identity.encode()).hexdigest()[:16],
            "profile": hashlib.sha256(prof.encode()).hexdigest()[:16]}


def evaluate_opportunity(opp: dict, job: dict | None, profile: dict,
                         observations: list[dict],
                         weights: RankingWeights | None = None) -> dict:
    """Build one versioned evaluation snapshot. Pure function of its inputs."""
    weights = weights or RankingWeights()
    kind = opp.get("kind")

    eligibility = evaluate_eligibility(
        kind, profile, title=opp.get("title"), description=opp.get("description"),
        company=(job or {}).get("company_name") or (opp.get("organization") or {}).get("name"),
        jd_location=(job or {}).get("location"),
        org_location=(opp.get("organization") or {}).get("location"),
    )

    if kind == "vacancy" and (job or {}).get("raw_text"):
        fit = _fit_from_jd(job["raw_text"], opp.get("title") or "", (job or {}).get("location") or "",
                           profile)
    elif kind == "vacancy":
        fit = _fit_from_jd("", opp.get("title") or "", (job or {}).get("location") or "",
                           profile)
    else:
        fit = _fit_without_jd(profile)

    competition = summarize_competition(observations)
    latest_obs = observations[0] if observations else None
    signals = derive_signals(opp, competition)
    priority = compute_priority(fit, opp.get("first_seen_at"), signals, weights)

    return {
        "eligibility_status": eligibility["status"],
        "eligibility_reasons": eligibility["reasons"],
        "eligibility_checks": eligibility["checks"],
        "fit_classification": fit["classification"],
        "fit_score": fit["score"],
        "fit_factors": fit["factors"],
        "fit_conflicts": fit["conflicts"],
        "fit_unknowns": fit["unknowns"],
        "competition": competition,
        "signals": signals,
        "priority_score": priority["score"],
        "contributions": priority["contributions"],
        "coverage": priority["coverage"],
        "config": {
            "formula_version": FORMULA_VERSION,
            "weights": weights.as_dict(),
            "freshness_max_age_days": FRESHNESS_MAX_AGE_DAYS,
            "input_hashes": _input_hashes(opp, profile),
        },
        "projection": {
            "eligibility_status": eligibility["status"],
            "fit_classification": fit["classification"],
            "fit_score": fit["score"],
            "competition_status": competition["status"],
            "competition_count": competition.get("observed_count"),
            "competition_comparable": bool(competition.get("comparable")),
            "competition_observed_at": (latest_obs.get("observed_at")
                                        if isinstance(latest_obs, dict) else None),
            "competition_platform": competition.get("platform"),
            "competition_meaning": competition.get("meaning"),
            "potentially_overlooked": bool(signals),
        },
    }
