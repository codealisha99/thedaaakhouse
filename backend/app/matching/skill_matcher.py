"""Skill matcher interface (milestone 2): JD requirements x CandidateProfile."""

from app.schemas.job import RequirementMatch


def match_requirements(requirements: list[str], candidate_skills: list[str]) -> list[RequirementMatch]:
    """Deterministic exact-match baseline. Semantic/evidence matchers layer on top."""
    skill_set = {s.lower() for s in candidate_skills}
    out: list[RequirementMatch] = []
    for req in requirements:
        if req.lower() in skill_set:
            out.append(RequirementMatch(requirement=req, status="matched", evidence=[req], confidence=1.0))
        else:
            out.append(RequirementMatch(requirement=req, status="missing", evidence=[], confidence=0.0))
    return out
