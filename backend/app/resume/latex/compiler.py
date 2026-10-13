"""Deterministic LaTeX editing layer (interface, milestone 2).

The LLM emits validated ResumeOperations, never raw LaTeX. This module will
own parse/find_entry/modify_bullet/reorder_entry/render/validate/compile.
`compile` will run `pdflatex` in an isolated temp dir and return captured logs.
"""
from dataclasses import dataclass, field


@dataclass
class LatexBullet:
    text: str


@dataclass
class LatexEntry:
    title: str
    bullets: list[LatexBullet] = field(default_factory=list)


@dataclass
class LatexDocument:
    sections: dict[str, list[LatexEntry]] = field(default_factory=dict)

    def render(self) -> str:
        raise NotImplementedError("milestone 2")

    def validate(self) -> list[str]:
        raise NotImplementedError("milestone 2")


def compile_latex(tex_source: str, timeout_s: int = 60) -> dict:
    """Compile .tex to PDF via pdflatex in an isolated temp dir.

    Returns {"compiled": bool, "status": str, "pdf": bytes|None, "log": str}.
    When pdflatex is absent the source is preserved and status explains
    exactly what is required — never presented as a successful PDF.
    """
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    if shutil.which("pdflatex") is None:
        return {"compiled": False, "status": "needs_latex_toolchain", "pdf": None,
                "log": "pdflatex not found. Install a LaTeX distribution "
                       "(e.g. TeX Live: `tlmgr`, macOS: MacTeX, Ubuntu: `apt install texlive-latex-base`) "
                       "to compile resume.tex to PDF."}
    with tempfile.TemporaryDirectory(prefix="thedaaakhouse-tex-") as tmp:
        tex_path = Path(tmp) / "resume.tex"
        tex_path.write_text(tex_source, encoding="utf-8")
        try:
            proc = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "resume.tex"],
                cwd=tmp, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return {"compiled": False, "status": "compile_timeout", "pdf": None,
                    "log": f"pdflatex timed out after {timeout_s}s"}
        pdf_path = Path(tmp) / "resume.pdf"
        if proc.returncode == 0 and pdf_path.exists():
            return {"compiled": True, "status": "compiled", "pdf": pdf_path.read_bytes(),
                    "log": proc.stdout[-2000:]}
        return {"compiled": False, "status": "compile_failed", "pdf": None,
                "log": (proc.stdout + proc.stderr)[-4000:]}
