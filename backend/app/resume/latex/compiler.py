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


def compile_latex(tex_source: str) -> bytes:
    """Compile to PDF via pdflatex in an isolated dir. Milestone 2."""
    raise NotImplementedError("pdflatex compilation lands in milestone 2")
