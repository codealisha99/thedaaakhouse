"""Truthfulness gate + export validation (milestone 2 interface).

`gate_edits` is the only accepted path for resume content changes produced
by the system: every line of a proposed edit must either exist verbatim in
the master resume, or map its factual atoms (metrics, lexicon skills,
multi-word proper nouns) back to the master text. A proposal is REJECTED —
never partially applied — when any atom is unsupported, so a made-up number,
employer or skill cannot enter a resume this app generates.

Limitation recorded honestly: employer/identity detection is heuristic
(Titlecase runs). Unknown capitalized BRAND names are treated as unsupported
unless present in the source — the gate fails closed.
"""

import re

from app.analysis.keywords import TECH_LEXICON, tokenize

_BULLET_PREFIX_RE = re.compile(r"^([\s]*(?:[•*·>]\s*|-\s+))(.*)$")
_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#._/'-]*")
_METRIC_TOKEN_RE = re.compile(r"\d[\d.,]*(?:\s*[%xX]|\s*[kKmM]\b)?")

# Sentence-initial action verbs are plain English, not identity claims; a
# leading Titlecase verb followed by an acronym ("Built RAG ...") must not
# become a proper-noun run. Same set is applied to master and proposal so a
# verb the source never used ("Delivered ...") still passes.
_LEAD_VERBS = {
    "built", "led", "used", "delivered", "drove", "owned", "created",
    "designed", "developed", "implemented", "improved", "launched",
    "managed", "reduced", "engineered", "shipped", "migrated", "ran",
    "automated", "cut", "grew", "scaled", "architected", "worked",
}

# letter-first alphanumeric tokens (k8s, gpt4, redis6-style) are technology
# tokens, not metrics — scrub before the metric scan so their digits are
# never mistaken for quantified achievements.
_ALNUM_TOKEN_RE = re.compile(r"(?<![\w\d.])[a-zA-Z]+\d+[a-zA-Z]*")


def _num_scan(s: str) -> list[str]:
    return _METRIC_TOKEN_RE.findall(_ALNUM_TOKEN_RE.sub(" ", s))


def _norm_text(s: str) -> str:
    """Lower, collapse whitespace, bullet markers stripped, keep word chars."""
    m = _BULLET_PREFIX_RE.match(s or "")
    body = m.group(2) if m else (s or "")
    words = re.findall(r"[A-Za-z0-9.+#/'-]+", body.casefold())
    return " ".join(w for w in words if w)


def _title_runs(s: str) -> list[tuple[str, str]]:
    """(normalized run, display run) of >=2 consecutive always-caps tokens.

    A line-leading action verb (see _LEAD_VERBS) is treated as sentence text
    and cannot start a run."""
    tokens_full = _TOKEN_RE.findall(s or "")
    tokens = tokens_full[1:] if (tokens_full and tokens_full[0].casefold() in _LEAD_VERBS) else tokens_full
    runs: list[tuple[str, str]] = []
    cur: list[str] = []
    for t in tokens:
        cap = bool(re.match(r"([A-Z0-9][A-Za-z0-9+#._/'-]*)", t) and (
            t == t.upper() or (t[:1].isupper() and (len(t) < 2 or t[1].islower()))))
        if cap and len(t) >= 2 and not t.isdigit():
            cur.append(t)
        else:
            if len(cur) >= 2:
                runs.append((" ".join(cur), " ".join(cur)))
            cur = []
    if len(cur) >= 2:
        runs.append((" ".join(cur), " ".join(cur)))
    return runs


# Surfaces whose canonical technology token is standard even though the
# surface form differs (used to accept alias switches like k8s -> Kubernetes).
# "k9s" intentionally absent: it is a different product, not an abbreviation
# of Kubernetes, and must never inherit its support.
_ALNUM_CANON = {"k8s": "kubernetes"}


def _alnum_tokens(text: str) -> set[str]:
    """letter-digit tokens (k8s / k9s / gpt4-style), lowercase, whole-surface."""
    out = set()
    for tok in _TOKEN_RE.findall(text or ""):
        if re.fullmatch(r"[a-zA-Z]+\d+[a-zA-Z]*", tok):
            out.add(tok.casefold())
    return out


def _master_atoms(master_text: str) -> dict:
    lines = [(l, _norm_text(l)) for l in (master_text or "").splitlines() if l.strip()]
    norm_lines = {n for _, n in lines}
    nums: list[str] = []
    for _, n in lines:
        nums += _num_scan(n)
    num_set = set(nums)
    tokens = set(tokenize(master_text or ""))
    runs = set()
    for l, _ in lines:
        for run_n, _d in _title_runs(l):
            runs.add(run_n.casefold())
    alnum = _alnum_tokens(master_text or "")
    return {"lines": norm_lines, "numbers": num_set, "tokens": tokens, "runs": runs,
            "alnum": alnum}


def _word_supported(tok: str, master_tokens: set) -> bool:
    """Verb/word-inflexion tolerant support: the exact token or a plain
    English inflection of it (built -> building, ship -> shipped) occurs in
    the master — reorder-only tailoring keeps inflections."""
    variants = {tok, tok + "s", tok + "es", tok + "ed", tok + "ing"}
    if tok.endswith("e"):
        variants |= {tok[:-1] + "ing"}
    if tok.endswith("s"):
        variants |= {tok[:-1]}
    if tok.endswith("ed") and len(tok) > 3:
        variants |= {tok[:-2]}
    if tok.endswith("ing") and len(tok) > 4:
        variants |= {tok[:-3], tok[:-3] + "e"}
    if tok in master_tokens or variants & master_tokens:
        return True
    # reverse direction: master inflections ("shipped") reduce to the stem
    for mt in master_tokens:
        if len(mt) - len(tok) in range(1, 4) and mt.startswith(tok[:2]):
            base = (mt[:-2] if mt.endswith("ed") and len(mt) > 4 else
                    mt[:-1] if mt.endswith("s") else
                    mt[:-3] if mt.endswith("ing") and len(mt) > 5 else mt)
            if base[:1] == tok[:1] and (tok.startswith(base[:max(2, len(base) - 1)])
                                        or base.startswith(tok[:max(2, len(base) - 1)])):
                return True
    return False


def _unsupported_reasons(proposal: str, atoms: dict) -> list[str]:
    if not atoms["lines"]:
        return ["master resume text is empty — cannot verify any claim"]
    n = _norm_text(proposal)
    if n and n in atoms["lines"]:
        return []  # verbatim: always supported
    reasons: list[str] = []
    seen = set()

    def note(msg: str) -> None:
        if msg not in seen:
            seen.add(msg)
            reasons.append(msg)

    for num in _num_scan(n):
        if num not in atoms["numbers"]:
            note(f"metric '{num}' does not occur in the source resume")
    toks = set(tokenize(proposal or ""))
    for tok in sorted(toks):
        # alias-aware membership: TECH_LEXICON and tokenize() resolve
        # abbreviations to canonical skill tokens, so an introduced lexicon
        # skill that never occurs in the master text is unsupported.
        if tok in TECH_LEXICON and tok not in atoms["tokens"]:
            note(f"skill '{tok}' does not occur in the source resume")
            break
    prop_alnum = _alnum_tokens(proposal)
    for a in sorted(prop_alnum):
        if a in atoms["alnum"]:
            continue
        canon = _ALNUM_CANON.get(a)
        if canon and canon in atoms["tokens"]:
            continue  # alias switch to the canonical term the master uses
        note(f"term '{a}' does not occur in the source resume")
        break
    for run_n, disp in _title_runs(proposal):
        run_l = run_n.casefold()
        if run_l in atoms["runs"]:
            continue
        run_tokens = set(tokenize(run_n))
        if run_tokens.issubset(atoms["tokens"]) or all(
                _word_supported(t, atoms["tokens"]) for t in run_tokens):
            continue  # every word exists in the source (inflexion-tolerant)
        note(f"proper noun '{disp}' does not occur in the source resume")
        break
    return reasons


def gate_edits(master_text: str, proposals: list[str] | str) -> dict:
    """Validate proposed resume content against the master resume.

    Returns {"accepted": [...], "rejected": [{"proposal", "reasons", "unsupported"}]}.
    A proposal is accepted only when fully supported; there is no partial
    application, so unsupported content never enters a generated resume.
    """
    if isinstance(proposals, str):
        proposals = [proposals]
    atoms = _master_atoms(master_text or "")
    accepted: list[str] = []
    rejected: list[dict] = []
    for raw in proposals or []:
        if not isinstance(raw, str) or not raw.strip():
            rejected.append({"proposal": str(raw), "reasons": ["empty proposal"],
                             "unsupported": []})
            continue
        reasons: list[str] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            reasons += _unsupported_reasons(line, atoms)
            if reasons:
                break
        if reasons:
            rejected.append({"proposal": raw, "reasons": reasons,
                             "unsupported": [r for r in reasons]})
        else:
            accepted.append(raw)
    return {"accepted": accepted, "rejected": rejected}


def ensure_supported(content: str, master_text: str) -> None:
    """Raise ValueError when generated resume content is not fully supported
    by the master resume. Safety net for the extraction pipeline."""
    result = gate_edits(master_text, [content])
    if result["rejected"]:
        reasons = "; ".join(result["rejected"][0]["reasons"][:3])
        raise ValueError(
            f"generated resume content failed the truthfulness gate: {reasons}")
