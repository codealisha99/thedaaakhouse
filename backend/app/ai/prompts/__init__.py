"""Prompt templates live here as versioned strings, not inline in services."""

JD_EXTRACTION_SYSTEM = """You extract structured job requirements from a job description.
Return JSON only. Never invent technologies not present in the text."""

RESUME_PARSE_SYSTEM = """You extract a structured candidate profile from resume text.
Return JSON matching the CandidateProfile schema. If a field is absent, use null/[].
Never invent experience, metrics, or skills."""
