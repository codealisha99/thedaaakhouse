"""Learning Hub generation + evaluation. Deterministic and grounded:

- Topics come only from the actual JD (skills/keywords), never a generic list.
- Lessons reference the candidate's real resume evidence where it exists.
- Knowledge checks are evaluated by expected-point coverage; missed points
  drive the follow-up. No LLM, no invented curriculum.
"""

from app.analysis.keywords import analyze_jd, tokenize

LEVELS = ["Fundamentals", "How it works", "In practice", "Advanced edges"]

EXERCISES = [
    "Explain {term} from first principles, as if to a sharp junior.",
    "Apply {term} to a problem in this role's domain; state your assumptions.",
    "Debug this: {term} is slow/wrong in production. List causes, then fixes.",
]


def _evidence_line(term: str, resume_lines: list[str]) -> str:
    for line in resume_lines:
        if term in set(tokenize(line)):
            return line.strip()[:200]
    return ""


def generate_study_plan(jd_text: str, resume_text: str = "", max_topics: int = 10) -> dict:
    if not (jd_text or "").strip():
        raise ValueError("job description text is empty")
    jd = analyze_jd(jd_text)
    resume_toks = set(tokenize(resume_text or ""))
    resume_lines = [l for l in (resume_text or "").splitlines() if l.strip()]

    topics: list[dict] = []
    seen: set[str] = set()
    for skill in jd["skills"][:max_topics]:
        known = skill in resume_toks
        topics.append(_topic(skill, known, resume_lines, priority=0 if not known else 1))
        seen.add(skill)
    for kw in jd["keywords"]:
        if len(topics) >= max_topics + 4 or kw["term"] in seen:
            continue
        topics.append(_topic(kw["term"], kw["term"] in resume_toks, resume_lines, priority=2))
        seen.add(kw["term"])
    topics.sort(key=lambda t: (t["priority"], t["term"]))
    for i, t in enumerate(topics):
        t["order"] = i + 1
    return {
        "topics": topics,
        "note": "Missing JD terms first. Known items are revision, not new study.",
    }


def _topic(term: str, known: bool, resume_lines: list[str], priority: int) -> dict:
    evidence = _evidence_line(term, resume_lines) if known else ""
    return {
        "term": term,
        "known": known,
        "priority": priority,
        "resume_evidence": evidence,
        "levels": [
            {"name": name, "prompt": f"{name}: {term}" + (
                f" — connect it to your experience: '{evidence}'" if evidence and i < 2 else "")}
            for i, name in enumerate(LEVELS)
        ],
        "exercises": [e.format(term=term) for e in EXERCISES],
        "check": {
            "question": f"Explain {term}: what it is, when to use it, and one production pitfall.",
            "expected_points": [
                f"definition of {term}",
                f"use case for {term}",
                f"pitfall or trade-off of {term}",
            ],
        },
    }


def evaluate_answer(answer: str, expected_points: list[str]) -> dict:
    """Score an answer by expected-point coverage. Returns verdict + feedback."""
    ans_toks = set(tokenize(answer or ""))
    hits, missed = [], []
    for point in expected_points or []:
        pt = set(tokenize(point)) - {"of", "for", "and", "the", "to", "a"}
        core = {t for t in pt if len(t) > 3}
        (hits if core and len(core & ans_toks) / len(core) >= 0.5 else missed).append(point)
    total = len(expected_points) or 1
    score = round(len(hits) / total, 3)
    verdict = "correct" if score >= 0.6 else "needs_revision"
    feedback = (
        "Solid — all key points covered." if verdict == "correct"
        else f"Missed: {'; '.join(missed)}. Revisit the lesson, then retry."
    )
    return {"score": score, "verdict": verdict, "hits": hits, "missed": missed,
            "feedback": feedback}
