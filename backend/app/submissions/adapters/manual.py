"""The manual-handoff adapter: no live provider access, honest about it.

Every real job board / ATS destination currently routes here. The handoff is
actionable, not a shrug: the user gets the destination URL and the frozen
package contents so nothing is lost when they submit by hand.
"""

from app.submissions.adapters import Adapter

REQUIRED_QUESTIONS: list[dict] = []


def build_manual() -> Adapter:
    return Adapter(
        name="manual",
        live=False,
        reason=(
            "no submission integration is configured for this destination; "
            "a frozen package is provided for manual application"
        ),
        required_questions=REQUIRED_QUESTIONS,
    )
