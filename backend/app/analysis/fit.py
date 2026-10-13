"""Career Fit Engine: JD x CareerProfile -> transparent classification.

Starting weights (product assumptions, NOT validated standards — see docs):
  direction 40% / tech+education 25% / transferable 20% / progression 15%.
Hard constraints (exclusions, eligibility blockers) always override scores.
Sparse/ambiguous JDs yield needs_review, never a confident verdict.
"""

from dataclasses import dataclass, field

from app.analysis.keywords import tokenize

DEFAULT_WEIGHTS = {"direction": 0.40, "tech_edu": 0.25, "transfer": 0.20, "progression": 0.15}

ADJACENCY: dict[str, list[str]] = {
    "ai engineer": ["ml engineer", "backend engineer", "data engineer", "software engineer", "research engineer"],
    "ml engineer": ["ai engineer", "data engineer", "backend engineer", "data scientist"],
    "backend engineer": ["software engineer", "devops engineer", "ml engineer", "ai engineer"],
    "frontend engineer": ["software engineer", "full stack", "ui engineer"],
    "data engineer": ["ml engineer", "backend engineer", "data scientist", "analytics engineer"],
    "data scientist": ["ml engineer", "data engineer", "analyst"],
    "devops engineer": ["backend engineer", "sre", "platform engineer"],
    "qa engineer": ["software engineer", "sdet", "test engineer"],
    "software engineer": ["backend engineer", "frontend engineer", "full stack", "ai engineer", "ml engineer"],
}

TARGET_SCORE = 0.65
ADJACENT_SCORE = 0.40


def _norm(s: str) -> str:
    return " ".join(tokenize(s or ""))


@dataclass
class FitConfig:
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    def normalized(self) -> dict:
        total = sum(self.weights.values()) or 1.0
        return {k: v / total for k, v in self.weights.items()}


def _user_years(profile: dict) -> float | None:
    best = None
    for exp in profile.get("experience", []) or []:
        try:
            y = float(exp.get("years", 0) or 0)
        except (TypeError, ValueError):
            continue
        best = y if best is None else max(best, y)
    return best


def classify_job(jd: dict, profile: dict, config: FitConfig | None = None) -> dict:
    """jd: analyze_jd() output (+title/company/location keys). profile: CareerProfile dict."""
    config = config or FitConfig()
    w = config.normalized()
    reasons, gaps, conflicts, unknown = [], [], [], []

    skills = list(jd.get("skills", []) or [])
    keywords = [k["term"] if isinstance(k, dict) else str(k) for k in (jd.get("keywords", []) or [])]
    title = str(jd.get("title", "") or "")
    category = str(jd.get("role_category", "") or "")
    responsibilities = " ".join(jd.get("responsibilities", []) or [])
    excerpt = str(jd.get("description_excerpt", "") or "")[:2000]
    blob = _norm(f"{title} {category} {responsibilities} {excerpt} {' '.join(skills)}")
    req_years = jd.get("experience_years")
    jd_location = str(jd.get("location", "") or "")
    if not skills and not keywords and not title.strip():
        return _verdict("needs_review", 0.0,
                        {"direction": 0, "tech_edu": 0, "transfer": 0, "progression": 0},
                        ["Job description has no extractable requirements."], [], [], ["empty JD"], config)

    demonstrated = {_norm(s) for s in (profile.get("skills_demonstrated", []) or []) if _norm(s)}
    claimed = {_norm(s) for s in (profile.get("skills_claimed", []) or []) if _norm(s)}
    targets = [_norm(t) for t in (profile.get("target_roles", []) or []) if _norm(t)]
    excluded = [_norm(e) for e in (profile.get("excluded_roles", []) or []) if _norm(e)]

    # ---- hard constraints ----
    forced_poor = None
    for exc in excluded:
        if exc and (exc in blob or blob in exc or any(exc in t or t in exc for t in [title.lower(), category.lower()])):
            forced_poor = f"Matches your exclusion '{exc}'."
            conflicts.append(forced_poor)
    years = _user_years(profile)
    if isinstance(req_years, (int, float)) and req_years > 0:
        if years is None:
            unknown.append("your years of experience (needed to check the requirement)")
        elif years + 1 < req_years and req_years - years >= 5:
            forced_poor = forced_poor or f"Requires {req_years:g}+ years; your profile shows {years:g}."
            conflicts.append(f"Experience blocker: requires {req_years:g}+ years, profile shows {years:g}.")
    pref_loc = str((profile.get("preferences", {}) or {}).get("location", "") or "").lower()
    if pref_loc and jd_location and pref_loc not in jd_location.lower() and jd_location.lower() not in pref_loc:
        conflicts.append(f"Location '{jd_location}' differs from your preference '{pref_loc}'.")

    # ---- direction (targets + adjacency on responsibilities, not title alone) ----
    title_hits = [t for t in targets if t and (t in blob or any(word in blob for word in t.split()))]
    adjacent_hits = []
    for t in targets:
        for adj in ADJACENCY.get(t, []):
            if adj in blob:
                adjacent_hits.append(adj)
    if title_hits:
        direction = 1.0
        reasons.append(f"Directly matches target role(s): {', '.join(title_hits)}.")
    elif adjacent_hits:
        direction = 0.55
        reasons.append(f"Adjacent to your targets via: {', '.join(sorted(set(adjacent_hits)))}.")
    elif targets:
        direction = 0.15
        gaps.append("No clear link to your target roles.")
    else:
        direction = 0.5
        unknown.append("your target roles (set them for sharper direction scoring)")

    # ---- tech + education ----
    matched = [s for s in skills if _norm(s) in demonstrated]
    claimed_hit = [s for s in skills if _norm(s) in claimed and _norm(s) not in demonstrated]
    tech = (len(matched) + 0.5 * len(claimed_hit)) / len(skills) if skills else 0.5
    if matched:
        reasons.append(f"Demonstrated skills match: {', '.join(matched[:6])}.")
    missing = [s for s in skills if _norm(s) not in demonstrated and _norm(s) not in claimed]
    learnable = [s for s in missing]
    gaps.extend(f"Missing skill: {s}." for s in learnable[:8])
    edu = profile.get("education", []) or []
    edu_text = _norm(" ".join(f"{e.get('degree','')} {e.get('field','')}" for e in edu if isinstance(e, dict)))
    edu_hit = bool(edu_text and any(word in edu_text for word in blob.split() if len(word) > 4))
    tech_edu = round(0.85 * tech + (0.15 if edu_hit else 0.0), 3)
    if edu_hit:
        reasons.append("Education background overlaps the role's domain.")

    # ---- transferable projects/experience ----
    corpus = _norm(" ".join(
        [str(p.get("name", "")) + " " + str(p.get("description", "")) for p in (profile.get("projects", []) or []) if isinstance(p, dict)]
        + [str(e.get("title", "")) + " " + str(e.get("description", "")) for e in (profile.get("experience", []) or []) if isinstance(e, dict)]
    ))
    key_terms = {_norm(s) for s in skills} | {k for k in (_norm(k) for k in keywords[:20]) if k}
    overlap = len([t for t in key_terms if t and t in corpus])
    transfer = round(min(1.0, overlap / 6), 3) if key_terms else 0.5
    if overlap:
        reasons.append(f"{overlap} role term(s) appear in your projects/experience.")
    else:
        gaps.append("No project/experience overlap found with role terms.")

    # ---- progression (seniority fit, bell-shaped; never rejects alone) ----
    if isinstance(req_years, (int, float)) and req_years > 0 and years is not None:
        diff = abs(years - req_years)
        progression = round(max(0.2, 1.0 - diff / 8), 3)
        reasons.append(f"Seniority fit: you {years:g}y vs required {req_years:g}y.")
    else:
        progression = 0.5
        if years is None:
            unknown.append("your experience timeline (needed for progression scoring)")

    factors = {"direction": round(direction, 3), "tech_edu": tech_edu,
               "transfer": transfer, "progression": progression}
    score = round(sum(factors[k] * w.get(k, 0) for k in factors), 3)

    if forced_poor:
        return _verdict("poor", min(score, 0.34), factors, reasons, gaps, conflicts, unknown, config,
                        recommendation="exclude")
    if score >= TARGET_SCORE and direction >= 0.55:
        return _verdict("target", score, factors, reasons, gaps, conflicts, unknown, config,
                        recommendation="prioritize")
    if score >= ADJACENT_SCORE:
        return _verdict("adjacent", score, factors, reasons, gaps, conflicts, unknown, config,
                        recommendation="consider")
    if not skills and len(keywords) < 5:
        return _verdict("needs_review", score, factors, reasons, gaps, conflicts, unknown, config)
    return _verdict("poor", score, factors, reasons, gaps, conflicts, unknown, config,
                    recommendation="exclude")


def _verdict(classification, score, factors, reasons, gaps, conflicts, unknown, config,
             recommendation=None):
    if recommendation is None:
        recommendation = {"target": "prioritize", "adjacent": "consider",
                          "poor": "exclude", "needs_review": "review"}[classification]
    return {"classification": classification, "score": score, "factors": factors,
            "reasons": reasons, "gaps": gaps, "conflicts": conflicts,
            "unknown": unknown, "recommendation": recommendation,
            "config": {"weights": config.normalized(),
                       "note": "Starting weights are product assumptions, not validated standards."}}
