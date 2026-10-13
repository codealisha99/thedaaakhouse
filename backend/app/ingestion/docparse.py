"""Document parsing for resume uploads: PDF/DOCX/TXT -> text + structure.

Distinguishes UPLOAD (bytes stored), PARSING (text out), and UNDERSTANDING.
Detects: empty docs, encrypted PDFs, image-only (scanned) PDFs needing OCR,
and section structure. Never claims parsed content it cannot extract.
"""

import io
import re

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".doc", ".docx", ".tex"}

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_SECTION_RES = {
    "summary": re.compile(r"^\s*(summary|objective|profile)\s*$", re.I),
    "experience": re.compile(r"^\s*(experience|employment|work history|work experience)\b", re.I),
    "education": re.compile(r"^\s*(education|academic|qualifications)\b", re.I),
    "skills": re.compile(r"^\s*(skills|technical skills|competencies|technologies)\b", re.I),
    "projects": re.compile(r"^\s*(projects|personal projects|selected work)\b", re.I),
    "certifications": re.compile(r"^\s*(certifications?|licenses?|credentials)\b", re.I),
}
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _split_sections(text: str) -> dict:
    sections: dict[str, list[str]] = {}
    current = "_head"
    sections[current] = []
    for line in (text or "").splitlines():
        s = line.strip()
        matched = False
        if s and len(s) < 60:
            for name, rx in _SECTION_RES.items():
                if rx.match(s):
                    current = name
                    sections.setdefault(current, [])
                    matched = True
                    break
        if not matched:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def _parse_pdf(data: bytes) -> tuple[str, list[str]]:
    from pypdf import PdfReader

    warnings: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:
        return "", [f"unreadable PDF: {e}"]
    if getattr(reader, "is_encrypted", False):
        try:
            if reader.decrypt("") == 0:
                return "", ["encrypted PDF: password required"]
        except Exception:
            return "", ["encrypted PDF: password required"]
    texts, image_pages = [], 0
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        texts.append(t)
        if not t.strip():
            try:
                if getattr(page, "images", None) and len(page.images) > 0:
                    image_pages += 1
            except Exception:
                pass
    text = "\n".join(texts)
    if not text.strip() and image_pages:
        warnings.append(f"image-only PDF ({image_pages} page(s) with images, no text): OCR required")
    elif not text.strip():
        warnings.append("PDF contained no extractable text")
    return text, warnings


def _parse_docx(data: bytes) -> tuple[str, list[str]]:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:
        return "", [f"unreadable DOCX: {e}"]
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    text = "\n".join(parts)
    if not text.strip():
        return "", ["DOCX contained no extractable text"]
    return text, []


def parse_upload(filename: str, content_type: str, data: bytes) -> dict:
    """Returns {text, sections, contact, warnings, parse_status}.

    parse_status: ok | empty | needs_ocr | failed.
    """
    ext = "." + ((filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else "")
    if ext not in ALLOWED_EXTENSIONS and ext != ".bin":
        return {"text": "", "sections": {}, "contact": {}, "warnings": [f"unsupported extension '{ext}'"],
                "parse_status": "failed"}
    warnings: list[str] = []
    if ext == ".pdf":
        text, warnings = _parse_pdf(data)
    elif ext in (".doc", ".docx"):
        if ext == ".doc":
            warnings.append(".doc is legacy: convert to DOCX for best extraction")
        text, w = _parse_docx(data)
        warnings += w
    else:
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception as e:
            return {"text": "", "sections": {}, "contact": {}, "warnings": [f"decode failed: {e}"],
                    "parse_status": "failed"}
    if not text.strip():
        if not warnings:
            warnings.append("document is empty")
        status = "needs_ocr" if any("OCR" in w for w in warnings) else ("failed" if any("unreadable" in w or "encrypted" in w for w in warnings) else "empty")
        return {"text": "", "sections": {}, "contact": {}, "warnings": warnings, "parse_status": status}
    sections = _split_sections(text)
    head = sections.get("_head", "") + "\n" + text[:800]
    emails = _EMAIL_RE.findall(head)
    phones = [p[0] if isinstance(p, tuple) else p for p in _PHONE_RE.findall(head)][:2]
    return {"text": text,
            "sections": sections,
            "contact": {"emails": sorted(set(emails))[:3], "phones": phones,
                        "years": sorted(set(_YEAR_RE.findall(text)))},
            "warnings": warnings, "parse_status": "ok"}
