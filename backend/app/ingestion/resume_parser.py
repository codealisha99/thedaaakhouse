"""Resume parser: deterministic structured extraction with evidence.

`EvidenceResumeParser` turns raw resume text into a validated
`CandidateProfile` where every entry carries a stable `EvidenceRef`
(`app.ingestion.evidence_extract`). Nothing is added that is not present in
the text: unparseable headings stay verbatim strings instead of invented
company/title values, and claimed skills stay distinct from demonstrated.
"""

import re

from app.ingestion.evidence_extract import extract_evidence
from app.ingestion.jd_parser import clean_text
from app.schemas.resume import (
    CandidateProfile,
    EducationEntry,
    EvidenceRef,
    ExperienceEntry,
    PersonalInformation,
    Project,
)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


class EvidenceResumeParser:
    """Deterministic primary parser (validated output, stable evidence refs).

    No structured-model provider is wired here today; deterministic
    extraction is both the primary path and the fallback (see
    docs/backend/implementation-progress.md).
    """

    def parse(self, raw_text: str, filename: str = "") -> CandidateProfile:
        cleaned = clean_text(raw_text).text
        evidence = extract_evidence(cleaned)

        emails: list[str] = []
        links: list[str] = []
        for item in [e for e in evidence if e["kind"] == "contact"]:
            emails += [m for m in _EMAIL_RE.findall(item["source_text"][:600]) if m not in emails]
            links += [l for l in item["fact"].get("links", []) if l not in links]

        first_line = cleaned.split("\n")[0].strip() if cleaned else ""
        name = first_line[:120] if first_line and len(first_line.split()) <= 6 else None

        experience: list[ExperienceEntry] = []
        for e in [x for x in evidence if x["kind"] == "experience"]:
            fact = e["fact"]
            heading = (fact.get("heading") or e["label"])[:120]
            # Company/title are only split when the heading literally contains a
            # comma; otherwise the whole heading is kept verbatim as company.
            parts = [p.strip() for p in (heading or "").split(",") if p.strip()]
            company = (parts[0][:120] if parts else heading) or "Experience"
            title = (parts[0][:120] if len(parts) > 1 else "")
            dates = fact.get("dates") or ""
            start, _, end = dates.partition("-")
            experience.append(ExperienceEntry(
                company=company,
                title=title or (fact.get("dates") or "Role"),
                start=start or None,
                end=end or None,
                bullets=list(fact.get("bullets", []))[:10],
            ))

        projects: list[Project] = []
        for e in [x for x in evidence if x["kind"] == "project"]:
            fact = e["fact"]
            heading = (fact.get("heading") or e["label"])[:120] or "Project"
            projects.append(Project(
                name=heading[:80],
                description=(fact.get("heading") or "")[:200],
                technologies=[t["label"] for t in evidence
                              if t["kind"] == "skill" and t["assert_type"] == "demonstrated"
                              and t["section"] == "projects"][:8],
                evidence=list(fact.get("bullets", []))[:6],
            ))

        education: list[EducationEntry] = []
        for e in [x for x in evidence if x["kind"] == "education"]:
            education.append(EducationEntry(
                institution=(e["fact"].get("text") or e["label"])[:160] or "Education entry",
            ))

        skills = [e["label"] for e in evidence
                  if e["kind"] == "skill" and e["assert_type"] == "claimed"][:50]
        achievements = [e["fact"].get("metric_verbatim", e["label"])
                        for e in evidence if e["kind"] == "achievement"][:20]
        certifications = [e["fact"].get("text", e["label"])
                          for e in evidence if e["kind"] == "certification"][:10]

        refs = [EvidenceRef(ev_id=e["ev_id"], kind=e["kind"], assert_type=e["assert_type"],
                            label=e["label"], section=e["section"],
                            line_start=e["line_start"], line_end=e["line_end"])
                for e in evidence]

        return CandidateProfile(
            personal_information=PersonalInformation(
                name=name,
                email=emails[0] if emails else None,
                links=list(dict.fromkeys(links))[:5],
            ),
            education=education,
            experience=experience,
            projects=projects,
            skills=skills,
            achievements=achievements,
            certifications=certifications,
            evidence=refs,
        )


def get_resume_parser() -> EvidenceResumeParser:
    return EvidenceResumeParser()
