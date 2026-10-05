"""Unit tests for deterministic helpers (no network, no DB)."""

from app.evaluation.factuality import claim_is_supported
from app.matching.skill_matcher import match_requirements


def test_factuality_gate_accepts_supported_claim():
    assert claim_is_supported(
        "Implemented vector retrieval using pgvector",
        ["Knowledge Assistant project: vector retrieval with pgvector"],
    )


def test_factuality_gate_rejects_invented_claim():
    assert not claim_is_supported(
        "Deployed Kubernetes clusters to production",
        ["Built a Streamlit demo, no infra work"],
    )


def test_skill_matcher_exact_baseline():
    out = match_requirements(["RAG", "Kubernetes"], ["rag", "python"])
    by_req = {m.requirement: m for m in out}
    assert by_req["RAG"].status == "matched"
    assert by_req["Kubernetes"].status == "missing"
