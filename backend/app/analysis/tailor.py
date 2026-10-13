"""Extractive resume tailoring. Strictly evidence-preserving:

- Never adds, rewrites, or deletes a line of the candidate's resume.
- Only REORDERS bullets locally within their own contiguous bullet group,
  highest JD-relevance first (recruiters read top bullets).
- Every operation carries reason + target requirement + source evidence.
- Missing JD terms are reported, never filled in.
"""

import re

from app.analysis.ats import analyze_ats
from app.analysis.keywords import analyze_jd, extract_skills

_BULLET_RE = re.compile(r"^([\s]*[-•*·>]\s+)(.*)$")


def _relevance(line: str, jd_terms: set[str], jd_skills: set[str],
               emphasis: set[str] | None = None) -> tuple[float, list[str]]:
    from app.analysis.keywords import tokenize

    toks = set(tokenize(line))
    hits = sorted(toks & jd_terms)
    skill_hits = sorted(toks & jd_skills)
    score = 2.0 * len(skill_hits) + 1.0 * len([h for h in hits if h not in skill_hits])
    if emphasis:
        score += 1.5 * len([h for h in hits if h in emphasis])
    return (score, hits)


def tailor_resume(resume_text: str, jd_text: str, emphasis: list[str] | None = None,
                  drop_irrelevant: bool = False) -> dict:
    """Extractive tailoring with per-attempt variation (still zero invention).

    emphasis: JD terms to weight extra — later attempts focus on still-missing
      terms so reorderings differ honestly.
    drop_irrelevant: move zero-JD-overlap bullets to a reported `omitted`
      list instead of the output (removal is listed, never hidden).
    """
    if not (resume_text or "").strip():
        raise ValueError("resume text is empty")
    jd = analyze_jd(jd_text)
    jd_terms = {k["term"] for k in jd["keywords"][:30]}
    jd_skills = set(jd["skills"])
    ats = analyze_ats(resume_text, jd_text)

    lines = resume_text.splitlines()
    out: list[str] = []
    changes: list[dict] = []
    omitted: list[str] = []
    emphasis_set = set(emphasis or [])

    def emit_bullet(idx: int, text: str, score: float, hits: list[str]) -> None:
        if drop_irrelevant and score == 0 and not hits:
            omitted.append(text.strip()[:200])
            return
        out.append(text)

    group: list[tuple[int, str, float, list[str]]] = []  # (orig_idx, text, score, hits)

    def flush_group() -> None:
        if not group:
            return
        if len(group) == 1 or all(g[2] == group[0][2] for g in group):
            for idx, text, score, hits in group:
                emit_bullet(idx, text, score, hits)
            changes.append({
                "operation": "keep",
                "target": f"{len(group)} bullet(s)",
                "reason": "equal JD relevance — original order preserved",
                "target_requirement": None,
                "source_evidence": [g[1].strip()[:160] for g in group[:3]],
            })
        else:
            ranked = sorted(group, key=lambda g: -g[2])
            if [g[0] for g in ranked] != [g[0] for g in group]:
                for idx, text, score, hits in ranked:
                    emit_bullet(idx, text, score, hits)
                top = ranked[0]
                changes.append({
                    "operation": "reorder_bullets",
                    "target": f"bullet group of {len(group)}",
                    "reason": f"JD emphasizes '{top[3][0]}'" if top[3] else "JD relevance ordering",
                    "target_requirement": (top[3][0] if top[3] else None),
                    "source_evidence": [t.strip()[:160] for _, t, _, _ in ranked[:2]],
                })
            else:
                for idx, text, score, hits in group:
                    emit_bullet(idx, text, score, hits)
                changes.append({
                    "operation": "keep",
                    "target": f"{len(group)} bullet(s)",
                    "reason": "already in JD-relevance order",
                    "target_requirement": None,
                    "source_evidence": [group[0][1].strip()[:160]],
                })
        group.clear()

    for i, line in enumerate(lines):
        m = _BULLET_RE.match(line)
        if m:
            score, hits = _relevance(m.group(2), jd_terms, jd_skills, emphasis_set)
            group.append((i, line, score, hits))
        else:
            flush_group()
            out.append(line)

    flush_group()
    tailored = "\n".join(out)

    resume_skills = set(extract_skills(resume_text))
    return {
        "content": tailored,
        "changes": changes,
        "omitted": omitted,
        "missing_keywords": ats["missing_keywords"],
        "skills_missing": ats["skills_missing"],
        "ats_before": ats["score"],
        "line_count_in": len(lines),
        "line_count_out": len(out),
        "note": "Extractive only: no lines added or rewritten. "
        "Omitted lines are listed, never hidden; missing JD terms are listed, not filled in.",
    }
