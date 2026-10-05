# Data model

## Principle

Raw text is **stored**; structured profiles are **used**. Every AI module reads
the validated Pydantic model, never the raw blob.

## CandidateProfile (`app/schemas/resume.py`)

```
personal_information: name | email | phone | location | links[]
education[]:          institution | degree | field | start | end | details[]
experience[]:         company | title | start | end | bullets[]
projects[]:           name | description | technologies[] | concepts[]
                      responsibilities[] | achievements[] | evidence[]
skills[]:             normalized skill strings
achievements[]:      free-text, each ideally traceable to evidence
certifications[]
```

`evidence[]` on a project is the load-bearing field: resume bullets may only
assert what evidence supports.

## JobDescription (`app/schemas/job.py`)

```
title | company | location | experience_level
responsibilities[] | required_skills[] | preferred_skills[]
qualifications[] | technologies[] | domain
raw_text | source_url
```

Plus `JobRequirement {requirement, category, importance, evidence_needed}` and
`RequirementMatch {requirement, status, evidence[], confidence}` where
`status ∈ matched | partial | missing | uncertain`.
`confidence` is internal-only — never shown without documented methodology.

## CompanyProfile (`app/schemas/company.py`)

Products, business model, engineering focus, technology signals, relevant
product/team, recent developments, role context — each claim joined to
`SourceRef {source_url, source_title, retrieved_at}`.

## Persistence (`app/db/models/`)

| Table | Key columns | Notes |
|---|---|---|
| resumes | filename, content_type, file_path, raw_text, profile JSON, parse_status | file on disk under `data/resumes/` |
| jobs | title, company_name, source_url, raw_text, structured JSON, status | `created → analyzed → matched → tailored` |
| companies | job_id, name, website, profile JSON, sources JSON | one research run per row |

## Status lifecycle (jobs)

```
created → analyzed → matched → tailored
              ↘ company_researched · interview_prepped · projects_recommended (parallel)
```

Long-running ops will later return `{job_id, status, progress, result, error}`
(pollable) instead of blocking the frontend.
