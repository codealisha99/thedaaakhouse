"""Resume PDF export: plain-text ATS-safe layout (no tables, no graphics).

Uses fpdf2 with built-in Helvetica so there is nothing to embed or break.
"""

import re

from fpdf import FPDF

from app.analysis.keywords import STOPWORDS as _STOPWORDS


def render_resume_pdf(label: str, content: str) -> bytes:
    pdf = FPDF(format="Letter")
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _latin(label[:90]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(120)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    for line in (content or "").splitlines():
        text = _latin(line.rstrip())
        if not text.strip():
            pdf.ln(4)
            continue
        bullet = text.lstrip().startswith(("-", "•", "*", "·", ">"))
        x = 15 if bullet else 10
        pdf.set_x(x)
        pdf.multi_cell(195 - x, 5, text.strip() if not bullet else text.strip()[1:].strip() or text.strip())
    return bytes(pdf.output())


def _latin(s: str) -> str:
    return s.encode("latin-1", errors="replace").decode("latin-1")


def validate_pdf_export(pdf_bytes: bytes, content: str) -> dict:
    """Reparse the exported PDF and verify the resume text actually appears
    in it — the honest-export guarantee: an unreadable or lossy PDF is never
    silently accepted as a valid export.

    Checks per non-empty master line (bullet-prefix insensitive) that its
    content words occur in the PDF text; coverage must be >= 0.7.
    """
    try:
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            raise ValueError("encrypted pdf")
        pages = len(reader.pages)
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # unreadable PDF is a hard error for the export
        return {"readable": False, "error": f"pdf unreadable: {exc}"}
    if not text.strip():
        return {"readable": False, "error": "pdf has no extractable text"}

    doc_stop =_STOPWORDS
    doc_tokens = {t for t in re.findall(r"[a-z0-9][a-z0-9+#./-]*", text.lower())}
    total = 0
    covered = 0
    misses: list[str] = []
    for line in (content or "").splitlines():
        s = line.strip()
        if not s:
            continue
        s = re.sub(r"^[\s]*([•*·>]|-)\s*", "", s)
        toks = [t for t in re.findall(r"[a-z0-9][a-z0-9+#./-]*", s.lower())
                if t not in doc_stop and len(t) > 1]
        if not toks:
            continue
        total += 1
        if all(t in doc_tokens or t.rstrip('.') in doc_tokens for t in toks):
            covered += 1
        else:
            misses.append(s[:120])
    coverage = round(covered / total, 3) if total else 1.0
    return {"readable": coverage >= 0.7, "pages": pages,
            "line_coverage": coverage, "uncovered_lines": misses[:10],
            "total_lines": total, "covered_lines": covered}


def reparse_pdf_export(pdf_bytes: bytes, content: str) -> dict:
    """Convenience wrapper kept for new call sites (gift from step 05)."""
    return validate_pdf_export(pdf_bytes, content)
