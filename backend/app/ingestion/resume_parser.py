"""Resume parser abstraction. Milestone 1: deterministic text extraction.

The interface returns a minimal CandidateProfile (name guess + skills guess
left EMPTY rather than invented). The LLM-backed parser plugs in later
behind `ResumeParser.parse` without changing callers.
"""

from abc import ABC, abstractmethod

from app.ingestion.jd_parser import clean_text
from app.schemas.resume import CandidateProfile, PersonalInformation


class ResumeParser(ABC):
    @abstractmethod
    def parse(self, raw_text: str, filename: str = "") -> CandidateProfile:
        ...


class BasicResumeParser(ResumeParser):
    """Deterministic stub: stores text, extracts nothing it can't prove.

    Deliberately returns an almost-empty profile — fabricating skills from
    keyword scans would violate the factuality rule.
    """

    def parse(self, raw_text: str, filename: str = "") -> CandidateProfile:
        cleaned = clean_text(raw_text).text
        first_line = cleaned.split("\n")[0].strip() if cleaned else ""
        name = first_line[:120] if first_line and len(first_line.split()) <= 6 else None
        return CandidateProfile(personal_information=PersonalInformation(name=name))


def get_resume_parser() -> ResumeParser:
    return BasicResumeParser()
