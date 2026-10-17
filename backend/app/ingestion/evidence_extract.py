"""Structured candidate evidence extraction — every fact carries its source.

Deterministic, no LLM. Rules:

- Nothing is reported that is not literally present in the resume text.
- Every fact cites a stable reference: ev_id (stable ordinal), section and
  1-based line span into the raw text, plus the quoted source lines.
- A skill found only in a skills list is `claimed`; the same lexicon skill
  inside an experience/projects bullet is `demonstrated` with that bullet as
  the source. Claimed does not imply demonstrated.
- Numbers/metrics are recorded verbatim as `stated` achievements — never
  recomputed, rounded or embellished, so a fabricated metric can never be
  traced to a source the user did not write.
"""

import re

from app.analysis.keywords import TECH_LEXICON, tokenize

BULLET_RE = re.compile(r"^([\s]*(?:[•*·]\s*|-\s+))(.*)$")
_METRIC_RE = re.compile(
    r"\d[\d.,]*\s*%|\$\s*\d|\b\d[\d.,]*\s*(?:k|m|mm|bn|billion|million|users|customers|clients|ms|s|hours?|days?)\b",
    re.I,
)
_YEAR_PAIR_RE = re.compile(r"\b((?:19|20)\d{2})\s*(?:-|–|—|to)\s*((?:19|20)\d{2}|present|current|now)\b", re.I)
_ITEM_SPLIT_RE = re.compile(r"[,;|]")

_MAX_SKILLS = 50
_MAX_DEMONSTRATED = 40
_MAX_ACHIEVEMENTS = 20
_MAX_GROUPS = 15


def _sections_with_spans(lines: list[str]) -> list[tuple[str, int, int]]:
    """(section_name, start_line, end_line_exclusive) in order. Head = '_head'."""
    from app.ingestion.docparse import _SECTION_RES

    bounds: list[tuple[str, int, int]] = []
    current, start = "_head", 0
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s or len(s) > 60:
            continue
        hit = next((name for name, rx in _SECTION_RES.items() if rx.match(s)), None)
        if hit:
            bounds.append((current, start, i))
            current, start = hit, i + 1
    bounds.append((current, start, len(lines)))
    return [(n, a, b) for n, a, b in bounds if any(l.strip() for l in lines[a:b])]


def _bullets_and_headings(lines: list[str]) -> list[tuple[str | None, list[str]]]:
    """[(heading, [bullet texts])] preserving original order."""
    groups: list[tuple[str | None, list[str]]] = []
    heading: str | None = None
    for raw in lines:
        m = BULLET_RE.match(raw)
        if m:
            text = m.group(2).strip()
            if text:
                if not groups or heading is not None:
                    groups.append((heading, []))
                    heading = None
                groups[-1][1].append(text)
        elif raw.strip():
            if groups and not groups[-1][1]:
                groups.pop()  # consecutive heading lines: last wins
            heading = raw.strip()
            groups.append((heading, []))
    # collapse: sequential entries without bullets keep the heading text only
    merged: list[tuple[str | None, list[str]]] = []
    for h, bs in groups:
        if not bs:
            merged.append((h, []))
        elif merged and merged[-1] == (h, []):
            merged[-1] = (h, bs)
        else:
            merged.append((h, bs))
    return [(h, bs) for h, bs in merged if h or bs]


def extract_evidence(text: str) -> list[dict]:
    """Deterministic fact extraction for one resume text.

    Returns dicts with: ev_id, kind, assert_type, label, fact, section,
    line_start, line_end (1-based inclusive), source_text.
    """
    if not (text or "").strip():
        return []
    lines = text.splitlines()
    items: list[dict] = []

    def add(kind: str, assert_type: str, label: str, fact: dict,
            section: str, a: int, b: int) -> None:
        items.append({
            "ev_id": f"ev{len(items) + 1}",
            "kind": kind,
            "assert_type": assert_type,
            "label": label[:160],
            "fact": fact,
            "section": section,
            "line_start": a + 1,
            "line_end": max(a + 1, b),
            "source_text": "\n".join(lines[a:b + 1])[:800],
        })

    for name, a, b in _sections_with_spans(lines):
        body = lines[a:b]
        if name == "_head":
            head_text = "\n".join(body)
            if re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", head_text[:600]):
                add("contact", "stated", "email/phone/links (header)",
                    {"raw": head_text[:300]}, "_head", a, min(b, a + 6))
            links = re.findall(r"https?://\S+", head_text[:600])
            if links:
                add("contact", "stated", "links (header)", {"links": links[:5],
                    "raw": head_text[:300]}, "_head", a, min(b, a + 6))
            continue
        if name in ("experience", "projects"):
            kind = "experience" if name == "experience" else "project"
            for heading, bullets in _bullets_and_headings(body)[:_MAX_GROUPS]:
                if not heading and not bullets:
                    continue
                fact: dict = {"heading": heading or ""}
                if bullets:
                    fact["bullets"] = bullets
                dates = _YEAR_PAIR_RE.search(heading or "") or \
                    _YEAR_PAIR_RE.search(" ".join(bullets[:2]) or "")
                if dates:
                    fact["dates"] = f"{dates.group(1)}-{dates.group(2)}"
                add(kind, "stated", (heading or (bullets[0] if bullets else "")), fact,
                    name, a, b)
            # demonstrated skills: lexicon tokens inside this section's bullets
            seen: set[str] = set()
            for bi, raw in enumerate(body):
                m = BULLET_RE.match(raw)
                if not m:
                    continue
                for tok in tokenize(m.group(2)):
                    if tok in TECH_LEXICON and tok not in seen:
                        seen.add(tok)
                        add("skill", "demonstrated", tok,
                            {"term": tok}, name, a + bi, a + bi)
                        if len(seen) >= _MAX_DEMONSTRATED:
                            break
                if len(seen) >= _MAX_DEMONSTRATED:
                    break
            # stated metric achievements (verbatim bullets that contain a metric)
            achieved = 0
            for bi, raw in enumerate(body):
                m = BULLET_RE.match(raw)
                if not m:
                    continue
                bullet = m.group(2).strip()
                if _METRIC_RE.search(bullet):
                    add("achievement", "stated", bullet[:160],
                        {"metric_verbatim": bullet.strip()[:200]}, name, a + bi, a + bi)
                    achieved += 1
                    if achieved >= _MAX_ACHIEVEMENTS:
                        break
            continue
        if name == "education":
            emitted = 0
            for bi, raw in enumerate(body[:10]):
                s = raw.strip()
                if s:
                    add("education", "stated", s[:160], {"text": s[:200]}, name, a + bi, a + bi)
                    emitted += 1
            continue
        if name == "certifications":
            for bi, raw in enumerate(body[:10]):
                s = raw.strip()
                if s:
                    add("certification", "stated", s[:160], {"text": s[:200]}, name, a + bi, a + bi)
            continue
        if name == "skills":
            seen: set[str] = set()
            for bi, raw in enumerate(body):
                stripped = raw.strip()
                m = BULLET_RE.match(stripped)
                candidates = (m.group(2) if m else stripped)
                for chunk in _ITEM_SPLIT_RE.split(candidates):
                    s = chunk.strip().strip("•*-·>").strip()
                    if not s or len(s) > 40:
                        continue
                    key = s.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    add("skill", "claimed", s[:160], {"term": s[:200]}, name, a + bi, a + bi)
                    if len(seen) >= _MAX_SKILLS:
                        break
                if len(seen) >= _MAX_SKILLS:
                    break
    return items
