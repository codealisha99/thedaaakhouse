"""Resume PDF export: plain-text ATS-safe layout (no tables, no graphics).

Uses fpdf2 with built-in Helvetica so there is nothing to embed or break.
"""

from fpdf import FPDF


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
