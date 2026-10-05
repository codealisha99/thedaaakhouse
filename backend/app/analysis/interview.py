"""Interview prep generation — every question carries category/reason/source.

Questions derive from actual JD terms and actual resume evidence, never from
a generic bank pretending to be analysis. Behavioral questions are labeled as
general (source: behavioral_general) so they can't be mistaken for derived ones.
"""

from app.analysis.keywords import analyze_jd, tokenize

TECH_TEMPLATES = [
    ("technical", "Explain your hands-on experience with {term}. What did you build and what broke?"),
    ("technical", "What are the key trade-offs when working with {term} in production?"),
    ("applied", "Walk me through how you'd use {term} to solve a problem in this role's domain."),
]

BEHAVIORAL = [
    "Tell me about a time you disagreed with a teammate on a technical decision. How did you resolve it?",
    "Describe a project that failed or missed its goal. What did you change afterwards?",
    "Tell me about the most complex system you've owned end to end.",
]


def generate_prep(jd_text: str, resume_text: str = "", company_name: str | None = None,
                  company_signals: list[str] | None = None, max_questions: int = 14) -> dict:
    jd = analyze_jd(jd_text)
    resume_toks = set(tokenize(resume_text or ""))
    terms = (jd["skills"] or [k["term"] for k in jd["keywords"]])[:8]

    questions: list[dict] = []
    topics = list(dict.fromkeys(terms))  # dedup, keep order
    for i, term in enumerate(terms):
        cat, tmpl = TECH_TEMPLATES[i % len(TECH_TEMPLATES)]
        questions.append({
            "question": tmpl.format(term=term),
            "category": cat,
            "reason": f"JD requires '{term}'",
            "source": "jd_requirement",
        })
        if term in resume_toks:
            questions.append({
                "question": f"Your resume mentions {term} — go deep: architecture, decisions, and what you'd do differently now?",
                "category": "resume_specific",
                "reason": f"Candidate resume contains '{term}' and JD requires it",
                "source": "candidate_resume",
            })
    for q in BEHAVIORAL:
        questions.append({"question": q, "category": "behavioral", "reason": "General behavioral round", "source": "behavioral_general"})
    for sig in (company_signals or [])[:2]:
        questions.append({
            "question": f"{company_name or 'The company'} shows investment in {sig} — how does your background map to that bet?",
            "category": "company_specific",
            "reason": f"Company research surfaced '{sig}'",
            "source": "company_research",
        })

    focus = [k["term"] for k in jd["keywords"][:30] if k["term"] not in resume_toks][:6]
    return {
        "topics": topics,
        "questions": questions[:max_questions],
        "focus_areas": focus,
        "note": "Derived from this JD and your resume text. Behavioral items are general-purpose.",
    }
