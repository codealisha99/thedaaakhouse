"""ATS analysis — a real computed breakdown, never a random number.

Score = 0.50·keyword_coverage + 0.25·skills + 0.15·experience + 0.10·formatting.
Every component shows its inputs so the score is auditable in the UI.
"""

import re

from app.analysis.keywords import TECH_LEXICON, analyze_jd, tokenize

_EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_SECTION_RE = re.compile(r"^(experience|education|skills|projects|summary|work history)\b", re.I | re.M)
_BULLET_RE = re.compile(r"^[\s]*[-•*·>] ", re.M)
_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)")


def analyze_ats(resume_text: str, jd_text: str) -> dict:
    if not (resume_text or "").strip():
        raise ValueError("resume text is empty")
    jd = analyze_jd(jd_text)
    resume_toks = set(tokenize(resume_text))

    # 1. Keyword coverage (weight-aware recall over JD top keywords)
    kws = jd["keywords"][:30]
    total_w = sum(k["weight"] for k in kws) or 1.0
    matched = [k["term"] for k in kws if k["term"] in resume_toks]
    matched_w = sum(k["weight"] for k in kws if k["term"] in resume_toks)
    keyword_match = round(100 * matched_w / total_w, 1)
    missing_keywords = [k["term"] for k in kws if k["term"] not in resume_toks][:20]

    # 2. Skills: required (lexicon hits in JD) vs present in resume
    required = jd["skills"]
    resume_lex = {t for t in resume_toks if t in TECH_LEXICON}
    matched_skills = [s for s in required if s in resume_lex]
    missing_skills = [s for s in required if s not in resume_lex]
    skills_match = round(100 * len(matched_skills) / len(required), 1) if required else 100.0

    # 3. Experience: max years mentioned in resume vs required
    req_years = jd["experience_years"]
    have_years = max([int(m.group(1)) for m in _YEARS_RE.finditer(resume_text)] or [0])
    if req_years:
        experience_match = round(min(100.0, 100 * have_years / req_years), 1)
    else:
        experience_match = 100.0

    # 4. Formatting / parseability checks (what real ATS parsers choke on)
    words = len(resume_text.split())
    checks = [
        {"check": "Contact email present", "passed": bool(_EMAIL_RE.search(resume_text))},
        {"check": "Phone number present", "passed": bool(_PHONE_RE.search(resume_text))},
        {"check": "Standard section headers", "passed": bool(_SECTION_RE.search(resume_text))},
        {"check": "Bullet points used", "passed": len(_BULLET_RE.findall(resume_text)) >= 3},
        {"check": "Reasonable length (300–6000 words)", "passed": 300 <= words <= 6000},
    ]
    formatting_score = round(100 * sum(c["passed"] for c in checks) / len(checks), 1)
    formatting_issues = [c["check"] for c in checks if not c["passed"]]

    score = round(
        0.50 * keyword_match + 0.25 * skills_match + 0.15 * experience_match + 0.10 * formatting_score,
        1,
    )

    recommendations: list[str] = []
    for term in missing_skills[:5]:
        recommendations.append(
            f"Add '{term}' — required by this JD but absent from your resume. "
            "Only add it where you have real experience."
        )
    for term in [k for k in missing_keywords if k not in missing_skills][:3]:
        recommendations.append(f"Mirror the JD keyword '{term}' in a relevant bullet, if truthful.")
    for issue in formatting_issues:
        recommendations.append(f"Fix formatting: {issue.lower()}.")
    if req_years and have_years < req_years:
        recommendations.append(
            f"JD asks for {req_years}+ years; your resume states {have_years}. "
            "Make tenures explicit if they support it."
        )
    if not recommendations:
        recommendations.append("Strong alignment — keep this version attached to the application.")

    return {
        "score": score,
        "keyword_match": keyword_match,
        "matched_keywords": matched,
        "missing_keywords": missing_keywords,
        "skills_required": required,
        "skills_matched": matched_skills,
        "skills_missing": missing_skills,
        "skills_match": skills_match,
        "experience_required_years": req_years,
        "experience_found_years": have_years,
        "experience_match": experience_match,
        "formatting_checks": checks,
        "formatting_score": formatting_score,
        "formatting_issues": formatting_issues,
        "recommendations": recommendations,
        "methodology": "0.50·keyword_coverage + 0.25·skills + 0.15·experience + 0.10·formatting",
    }
