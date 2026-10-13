"""LaTeX resume generation: structured content -> ATS-friendly .tex source.

Single-column article layout, standard headings, no graphics. Every string
is escaped; content comes only from the candidate's verified resume text.
"""

import re

_SECTION_TITLES = [
    ("summary", "Summary"),
    ("experience", "Experience"),
    ("education", "Education"),
    ("skills", "Skills"),
    ("projects", "Projects"),
    ("certifications", "Certifications"),
]

_BULLET_RE = re.compile(r"^[\s]*[-•*·>]\s+(.*)$")


def escape_latex(s: str) -> str:
    return (
        s.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&").replace("%", "\\%").replace("$", "\\$")
        .replace("#", "\\#").replace("_", "\\_")
        .replace("{", "\\{").replace("}", "\\}")
        .replace("~", "\\textasciitilde{}").replace("^", "\\textasciicircum{}")
    )


def build_latex(name: str, contact_lines: list[str], sections: dict[str, str],
                tail_lines: list[str] | None = None) -> str:
    """Assemble a complete .tex document. sections: name -> body text."""
    parts = [
        "\\documentclass[11pt]{article}",
        "\\usepackage[margin=0.7in]{geometry}",
        "\\usepackage[hidelinks]{hyperref}",
        "\\usepackage{enumitem}",
        "\\setlist[itemize]{leftmargin=*,itemsep=1pt,topsep=2pt}",
        "\\pagestyle{empty}",
        "\\begin{document}",
        f"\\begin{{center}}{{\\Large\\textbf{{{escape_latex(name)}}}}}",
    ]
    for line in (contact_lines or [])[:3]:
        if line.strip():
            parts.append(f"\\\\{escape_latex(line.strip())}")
    parts.append("\\end{center}")
    parts.append("")
    for key, title in _SECTION_TITLES:
        body = (sections.get(key, "") or "").strip()
        if not body:
            continue
        parts.append(f"\\section*{{{title}}}")
        items, prose = [], []
        for raw in body.splitlines():
            m = _BULLET_RE.match(raw)
            if m and m.group(1).strip():
                items.append(m.group(1).strip())
            elif raw.strip():
                prose.append(raw.strip())
        for p in prose:
            parts.append(escape_latex(p))
            parts.append("")
        if items:
            parts.append("\\begin{itemize}")
            parts.extend(f"\\item {escape_latex(it)}" for it in items)
            parts.append("\\end{itemize}")
        parts.append("")
    if tail_lines:
        parts.append("\\section*{Additional}")
        parts.append("\\begin{itemize}")
        parts.extend(f"\\item {escape_latex(t)}" for t in tail_lines if t.strip())
        parts.append("\\end{itemize}")
    parts.append("\\end{document}")
    return "\n".join(parts) + "\n"


def validate_latex(tex: str) -> dict:
    """Structural checks only (no compilation). Returns {valid, issues}."""
    issues = []
    if "\\documentclass" not in tex:
        issues.append("missing \\documentclass")
    if "\\begin{document}" not in tex or "\\end{document}" not in tex:
        issues.append("missing document environment")
    if tex.count("{") != tex.count("}"):
        issues.append("unbalanced braces")
    if tex.count("\\begin{itemize}") != tex.count("\\end{itemize}"):
        issues.append("unbalanced itemize environments")
    for pat, label in [(r"(?<!\\)%", "unescaped %"), (r"(?<!\\)&(?!.*\\\\)", None)]:
        if label and re.search(pat, tex):
            issues.append(label)
    if "\\section*" not in tex:
        issues.append("no sections generated")
    return {"valid": not issues, "issues": issues}
