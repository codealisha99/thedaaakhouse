"""Factuality gate — the hallucination firewall (interface, milestone 2).

Design (see docs/architecture.md):
    Generated claim -> Candidate evidence lookup -> ACCEPT or REJECT.
Milestone 1 ships the pure rule function so tests pin the behavior early.
"""


def claim_is_supported(claim: str, evidence_texts: list[str]) -> bool:
    """Return True iff any evidence text mentions a salient token of the claim.

    Deliberately conservative token-overlap heuristic; the LLM-backed version
    plugs in later behind the same function signature.
    """
    tokens = {t.strip(".,;:()[]").lower() for t in claim.split() if len(t) > 3}
    blob = " ".join(evidence_texts).lower()
    return any(t in blob for t in tokens)
