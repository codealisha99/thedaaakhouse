"""Job-specific ATS compatibility, v2. Deterministic and transparent.

Stages per requirement: exact -> alias -> partial -> semantic-lite.
Weights (experimental defaults, configurable): skills 35 / experience 20 /
projects 15 / education 10 / semantic 10 / parse 10.
Unevaluable categories are reported unknown and EXCLUDED from the total
(renormalized), never silently zeroed. Mandatory blockers stay separate.
Score = thedaaakhouse compatibility estimate, NOT an employer's ATS score.
"""

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.analysis.keywords import TECH_LEXICON, analyze_jd, tokenize

DEFAULT_WEIGHTS = {"skills": 0.35, "experience": 0.20, "projects": 0.15,
                   "education": 0.10, "semantic": 0.10, "parse": 0.10}

ALIASES = {
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "k8s": "kubernetes",
    "js": "javascript", "ts": "typescript",
    "torch": "pytorch",
    "postgres": "postgresql", "pg": "postgresql",
    "mongo": "mongodb",
    "gh actions": "github actions",
    "ci/cd": "ci cd",
    "nodejs": "node.js", "node": "node.js",
    "reactjs": "react", "nextjs": "next.js",
    "aws": "amazon web services", "gcp": "google cloud",
    "ml": "machine learning", "ai": "artificial intelligence",
    "nlp": "natural language processing",
}
# Removed from ALIASES deliberately (honesty):
#   "k9s": k9s is a distinct product (kubectl CLI), not an abbreviation of
#          Kubernetes; aliasing it inflated skill matches the resume does
#          not evidence.
#   "tf":  "tf" is too ambiguous ("TensorFlow", "Terraform", "team fortress");
#          mapping it fabricated TensorFlow matches.
#   "gha": same ambiguity; only the full "gh actions"/"github actions"
#          surface is mapped.

_PREF_RE = re.compile(r"(preferred|nice to have|bonus|plus|desired|pluses|optional)", re.I)
_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)", re.I)
_DEGREE_RES = {
    "bachelor": re.compile(r"\b(bachelor|b\.?s\.?|b\.?a\.?|undergraduate|btech|b\.tech)\b", re.I),
    "master": re.compile(r"\b(master|m\.?s\.?|m\.?a\.?|mba|mtech|m\.tech|graduate degree)\b", re.I),
    "phd": re.compile(r"\b(ph\.?d\.?|doctorate)\b", re.I),
}


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    return ALIASES.get(s, s)


def _vec(toks: list[str]) -> Counter:
    return Counter(t for t in toks if len(t) > 2)


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[t] * b[t] for t in a.keys() & b.keys())
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def split_requirements(jd_text: str) -> tuple[list[str], list[str]]:
    """Required vs preferred JD skills, from section cues. Both lexicon-grounded."""
    required_lines, preferred_lines, in_pref = [], [], False
    for line in (jd_text or "").splitlines():
        s = line.strip()
        if re.match(r"^(requirements|required|must have|qualifications)\b", s, re.I) and len(s) < 80:
            in_pref = False
            required_lines.append(re.sub(r"^[^:]*:\s*", "", s))
            continue
        if _PREF_RE.search(s) and len(s) < 120:
            in_pref = True
            # header often carries skills inline ("Preferred: Go, Rust")
            rest = re.sub(r"^[^:]*:\s*", "", s)
            (preferred_lines if in_pref else required_lines).append(rest)
            continue
        (preferred_lines if in_pref else required_lines).append(s)
    req = sorted({_norm(t) for t in _lex("\n".join(required_lines))})
    pref = sorted({_norm(t) for t in _lex("\n".join(preferred_lines)) if t not in req})
    return req, pref


def _lex(text: str) -> list[str]:
    counts = Counter(t for t in tokenize(text) if t in TECH_LEXICON or _norm(t) in TECH_LEXICON)
    return [t for t, _ in counts.most_common()]


def _years_max(text: str) -> int:
    found = [int(m.group(1)) for m in _YEARS_RE.finditer(text or "")]
    return max(found) if found else 0


_MONTH_NUM = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}

# Month YYYY [– Month YYYY | YYYY | Present]
_RES_RANGE = re.compile(
    r"\b(" + "|".join(_MONTH_NUM) + r")[a-z]*\.?\s+(\d{4})\s*(?:-|–|—|to)\s*"
    r"(?:(?:" + "|".join(_MONTH_NUM) + r")[a-z]*\.?\s+(\d{4})|(\d{4})|(present|current|now))\b", re.I)
# MM/YYYY [– MM/YYYY | Present]
_RES_MY = re.compile(r"\b(\d{1,2})/(\d{4})\s*(?:-|–|—|to)\s*(?:(\d{1,2})/(\d{4})|(present|current|now))\b")
# [Month] YYYY – [Month] YYYY | Present  (year-only form)
_RES_YY = re.compile(
    r"\b(?:" + "|".join(_MONTH_NUM) + r"[a-z]*\.?\s+)?((?:19|20)\d{2})\s*(?:-|–|—|to)\s*"
    r"(?:(?:" + "|".join(_MONTH_NUM) + r"[a-z]*\.?\s+)?((?:19|20)\d{2})|(present|current|now))\b", re.I)


def _month_year(mn, yr) -> int:
    return yr * 12 + (mn or 6)  # month-less years count a mid-year month


def _date_span_years(text: str) -> float:
    """Sum of non-overlapping employment spans derived from date ranges in
    the text (Month YYYY, MM/YYYY, YYYY forms with 'Present' endings), in
    years. Deterministic and honest: nothing is inferred the text does not
    literally state."""
    spans: list[tuple[int, int]] = []
    now = datetime.now(timezone.utc)
    now_month_year = now.year * 12 + now.month

    def months(mn, yr):
        try:
            return _month_year(mn, int(yr))
        except (TypeError, ValueError):
            return None

    for text_pat in ((text or ""),):
        for m in _RES_RANGE.finditer(text_pat):
            start = months(_MONTH_NUM.get(str(m.group(1)).lower()[:3]), m.group(2))
            end = (months(_MONTH_NUM.get(str(m.group(3)).lower()[:3]), m.group(4))
                   if m.group(3) and m.group(4) else
                   (months(None, m.group(4)) if m.group(4) else now_month_year))
            if start is not None and end is not None and end >= start:
                spans.append((start, end))
        for m in _RES_MY.finditer(text_pat):
            start = months(int(m.group(1)), m.group(2))
            end = (months(int(m.group(3)), m.group(4))
                   if m.group(3) and m.group(4) else now_month_year)
            if start is not None and end is not None and end >= start:
                spans.append((start, end))
        for m in _RES_YY.finditer(text_pat):
            start = months(None, m.group(1))
            end = months(None, m.group(2)) if m.group(2) else now_month_year
            if start is not None and end is not None and end >= start:
                spans.append((start, end))

    if not spans:
        return 0.0
    spans.sort()
    total = 0
    cur_s, cur_e = spans[0]
    for s, e in spans[1:]:
        if s > cur_e:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    total += cur_e - cur_s
    return round(max(0, total) / 12.0, 1)


@dataclass
class AtsConfig:
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    def normalized(self, known: list[str]) -> dict:
        total = sum(self.weights.get(k, 0) for k in known) or 1.0
        return {k: self.weights.get(k, 0) / total for k in known}


def analyze_ats_v2(resume_text: str, jd_text: str, parsed_doc: dict | None = None,
                   config: AtsConfig | None = None) -> dict:
    if not (resume_text or "").strip():
        raise ValueError("resume text is empty")
    config = config or AtsConfig()
    jd = analyze_jd(jd_text)
    required, preferred = split_requirements(jd_text)
    resume_toks = set(tokenize(resume_text))
    norm_toks = {_norm(t) for t in resume_toks}

    sections = (parsed_doc or {}).get("sections") or {}
    sec_toks = {name: set(tokenize(body)) for name, body in sections.items() if isinstance(body, str)}
    sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", resume_text) if len(s.strip()) > 15]
    sent_vecs = [(s, _vec(tokenize(s))) for s in sentences]

    matched, partial, missing = [], [], []

    phrases = [p for p in (jd.get("phrases", []) or [])[:8]
               if len(p.split()) > 1 and p not in {r for r in required}]

    def evidence_for(skill: str) -> tuple[str, list[str], str]:
        """-> (match_kind, evidence_lines, strength)."""
        if skill in norm_toks:
            lines = [l.strip()[:200] for l in resume_text.splitlines()
                     if skill in {_norm(t) for t in tokenize(l)}][:3]
            strong = any(skill in sec_toks.get(sec, set()) or
                         skill in {_norm(t) for t in sec_toks.get(sec, set())}
                         for sec in ("experience", "projects"))
            return "exact", lines, ("strong" if strong else "documented")
        for alias, canon in ALIASES.items():
            alias_words = alias.split()
            if skill == canon and all(w in resume_toks for w in alias_words):
                return "alias", [f"found as '{alias}'"], "documented"
            if skill == alias and canon in resume_toks:
                return "alias", [f"found as '{canon}'"], "documented"
        words = [w for w in skill.split() if len(w) > 2]
        if len(words) >= 2 and sum(1 for w in words if w in resume_toks) > len(words) / 2:
            return "partial", [f"partial term overlap: {skill}"], "mentioned"
        best, best_s = 0.0, ""
        qv = _vec(tokenize(skill))
        for s, sv in sent_vecs:
            sim = _cosine(qv, sv)
            if sim > best:
                best, best_s = sim, s
        if best >= 0.20:
            return "semantic", [f"semantically similar ({best:.2f}): {best_s[:200]}"], "mentioned"
        return "missing", [], ""

    for skill in required:
        kind, ev, strength = evidence_for(skill)
        entry = {"requirement": skill, "kind": kind, "evidence": ev, "strength": strength,
                 "priority": "required"}
        (matched if kind != "missing" else missing).append(entry)
        if kind == "partial":
            partial.append(entry)
    for skill in preferred:
        kind, ev, strength = evidence_for(skill)
        if kind == "missing":
            missing.append({"requirement": skill, "kind": "missing", "evidence": [],
                            "strength": "", "priority": "preferred"})
        else:
            matched.append({"requirement": skill, "kind": kind, "evidence": ev,
                            "strength": strength, "priority": "preferred"})
    for phrase in phrases:
        kind, ev, strength = evidence_for(phrase)
        entry = {"requirement": phrase, "kind": kind, "evidence": ev,
                 "strength": strength, "priority": "phrase"}
        (matched if kind != "missing" else missing).append(entry)
        if kind == "partial":
            partial.append(entry)

    cats: dict[str, dict] = {}
    # skills: required full weight, preferred 0.25 (light dent only), phrases 0.6
    if required or preferred or phrases:
        got = sum(1.0 for e in matched if e["priority"] == "required")
        got += sum(0.25 for e in matched if e["priority"] == "preferred")
        got += sum(0.6 for e in matched if e.get("priority") == "phrase")
        total = len(required) + 0.25 * len(preferred) + 0.6 * len(phrases)
        cats["skills"] = {"score": round(100 * got / total, 1) if total else 0.0,
                          "detail": f"{len([e for e in matched if e['priority']=='required'])}/{len(required)} required, "
                                    f"{len([e for e in matched if e['priority']=='preferred'])}/{len(preferred)} preferred"}
    else:
        cats["skills"] = {"score": None,
                          "detail": "unknown: JD states no technical requirements"}
    # experience: years are used only when countably evidenced — stated
    # ("n years") or derivable from the resume's own date ranges. When the
    # resume evidences neither, the category stays unknown (no guessed score,
    # no fabricated blocker).
    req_years = jd.get("experience_years") or _years_max(jd_text)
    stated_years = _years_max(resume_text)
    date_years = _date_span_years(resume_text)
    if stated_years:
        have_years, years_src = stated_years, "stated"
    elif date_years:
        have_years, years_src = date_years, "from date ranges"
    else:
        have_years, years_src = None, "none"
    if req_years and have_years is not None:
        cats["experience"] = {"score": round(min(100.0, 100 * have_years / req_years), 1),
                              "detail": f"requires {req_years}y, resume shows {have_years}y ({years_src})"}
    elif req_years:
        cats["experience"] = {"score": None,
                              "detail": (f"unknown: JD requires {req_years}y but the resume has no stated "
                                         "years and no countable date ranges — score never guessed")}
    elif have_years is not None:
        cats["experience"] = {"score": 100.0,
                              "detail": f"no JD requirement; resume shows {have_years}y ({years_src})"}
    else:
        cats["experience"] = {"score": None, "detail": "unknown: neither JD nor resume states years"}
    # projects: practical evidence share
    if matched:
        strong = sum(1 for e in matched if e["strength"] == "strong")
        cats["projects"] = {"score": round(100 * strong / len(matched), 1),
                            "detail": f"{strong}/{len(matched)} matches evidenced in experience/projects sections"}
    else:
        cats["projects"] = {"score": 0.0, "detail": "no matched skills to evidence"}
    # education
    edu_reqs = [k for k in _DEGREE_RES if _DEGREE_RES[k].search(jd_text or "")]
    edu_text = (sections.get("education", "") + " " + resume_text[:2000]).lower()
    if edu_reqs:
        hit = [k for k in edu_reqs if _DEGREE_RES[k].search(edu_text)]
        cats["education"] = {"score": 100.0 if hit else 0.0,
                             "detail": f"JD asks {', '.join(edu_reqs)}; resume shows {', '.join(hit) or 'none'}"}
    else:
        cats["education"] = {"score": None, "detail": "unknown: JD states no education requirement"}
    # semantic: mean best-similarity over required
    if required:
        sims = []
        for skill in required:
            qv = _vec(tokenize(skill))
            sims.append(max([_cosine(qv, sv) for _, sv in sent_vecs] or [0.0]))
        cats["semantic"] = {"score": round(100 * sum(sims) / len(sims), 1),
                            "detail": "mean best-sentence cosine over required skills (token vectors, no LLM)"}
    else:
        cats["semantic"] = {"score": None, "detail": "unknown: no required skills to compare"}
    # parse
    if parsed_doc is None:
        cats["parse"] = {"score": None, "detail": "unknown: document was ingested before structured parsing"}
    else:
        warnings = (parsed_doc or {}).get("warnings", []) or []
        failed = any("unreadable" in w or "encrypted" in w for w in warnings)
        cats["parse"] = {"score": 0.0 if failed else max(0.0, 100 - 15 * len(warnings)),
                         "detail": "; ".join(warnings) or "clean parse with section structure"}

    known = [k for k, v in cats.items() if v["score"] is not None]
    weights = config.normalized(known)
    score = round(sum(cats[k]["score"] * weights[k] for k in known), 1) if known else 0.0
    for k in known:
        cats[k]["weight"] = round(weights[k], 3)
        cats[k]["contribution"] = round(cats[k]["score"] * weights[k], 1)

    blockers = []
    if req_years and have_years is not None and req_years - have_years >= 5:
        stated = f"{have_years}y ({years_src})"
        blockers.append(f"Experience blocker: requires {req_years}y, resume shows {stated}.")
    if edu_reqs and cats["education"]["score"] == 0:
        blockers.append(f"Education blocker: JD asks {', '.join(edu_reqs)}, resume shows none.")
    if cats["parse"]["score"] == 0 and parsed_doc is not None:
        blockers.append("Document blocker: resume could not be parsed (see warnings).")

    recs = []
    for e in missing:
        if e["priority"] == "required":
            recs.append(f"Missing required: '{e['requirement']}' — add only with real experience.")
    for e in [m for m in matched if m["strength"] == "documented"]:
        recs.append(f"Documented but not proven: '{e['requirement']}' appears only in a skills list — move it into a project bullet with evidence.")
    for w in (parsed_doc or {}).get("warnings", []) or []:
        recs.append(f"Parseability: {w}.")
    if cats["experience"]["score"] is None and req_years:
        recs.append(f"JD expects {req_years}y experience; make tenures explicit (start/end dates or stated years) so it can be evaluated — the score is left unknown, not guessed.")
    elif cats["experience"]["score"] is not None and cats["experience"]["score"] < 100 and req_years:
        recs.append("Make tenures explicit (start/end dates) so experience is countable.")
    if not recs:
        recs.append("Strong alignment across all evaluable categories.")

    return {
        "ats_version": 2,
        "score": score,
        "categories": cats,
        "matched": matched, "partial": [e for e in matched if e["kind"] == "partial"],
        "missing": missing,
        "blockers": blockers,
        "recommendations": recs,
        "weights": dict(config.weights),
        "methodology": ("Weighted mean over evaluable categories only; unknown categories "
                        "excluded (renormalized). Weights configurable; defaults are experimental."),
        "provenance": {"jd_sha256": hashlib.sha256((jd_text or "").encode()).hexdigest()[:16],
                       "resume_chars": len(resume_text or "")},
    }
