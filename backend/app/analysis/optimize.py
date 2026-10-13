"""Optimize-loop decisions: pure functions, no DB, fully unit-testable.

Policy: initial < trigger_below -> tailor; accept at >= accept_at_least;
at most max_attempts. Plateau (two consecutive attempts without beating the
best score) stops early with an honest target_not_reached.
"""

from dataclasses import dataclass


@dataclass
class OptimizePolicy:
    trigger_below: float = 90.0
    accept_at_least: float = 92.0
    max_attempts: int = 3

    def validate(self) -> None:
        if not (0 < self.trigger_below <= 100):
            raise ValueError("trigger_below must be in (0, 100]")
        if not (0 < self.accept_at_least <= 100):
            raise ValueError("accept_at_least must be in (0, 100]")
        if self.accept_at_least < self.trigger_below:
            raise ValueError("accept_at_least must be >= trigger_below")
        if not (1 <= self.max_attempts <= 10):
            raise ValueError("max_attempts must be in [1, 10]")

    def as_dict(self) -> dict:
        return {"trigger_below": self.trigger_below,
                "accept_at_least": self.accept_at_least,
                "max_attempts": self.max_attempts}


def plan_next_attempt(attempt_number: int, missing_terms: list[str]) -> dict:
    """Honest per-attempt variation (reordering focus only, never new content)."""
    if attempt_number <= 1:
        return {"emphasis": [], "drop_irrelevant": False,
                "strategy": "reorder by JD relevance"}
    if attempt_number == 2:
        return {"emphasis": list(missing_terms)[:8], "drop_irrelevant": False,
                "strategy": "reorder emphasizing still-missing terms"}
    return {"emphasis": list(missing_terms)[:8], "drop_irrelevant": True,
            "strategy": "emphasize missing terms; move zero-overlap bullets to reported omitted list"}


def should_stop(attempt_scores: list[float], policy: OptimizePolicy) -> tuple[bool, str]:
    """Decide after recording the latest attempt score (initial score counts
    as the baseline best when no attempts exist — pass [initial] + attempts)."""
    if not attempt_scores:
        return False, ""
    best = max(attempt_scores)
    if best >= policy.accept_at_least:
        return True, "acceptance threshold reached"
    made = len(attempt_scores) - 1  # attempts excluding the initial baseline
    if made >= policy.max_attempts:
        return True, f"max attempts ({policy.max_attempts}) reached"
    # Plateau needs a full window: it can only stop from the 4th score on,
    # so the default policy (max 3) always runs all three attempts.
    if len(attempt_scores) >= 4:
        recent_best = max(attempt_scores[:-2])
        if max(attempt_scores[-2:]) <= recent_best:
            return True, "score plateaued: two attempts without improvement"
    return False, ""


def final_status(initial_score: float, attempts: list[dict], policy: OptimizePolicy) -> str:
    if initial_score >= policy.accept_at_least:
        return "accepted"
    if initial_score >= policy.trigger_below:
        return "target_not_reached"
    if not attempts:
        return "target_not_reached"
    best = max([initial_score] + [a["score"] for a in attempts])
    return "accepted" if best >= policy.accept_at_least else "target_not_reached"
