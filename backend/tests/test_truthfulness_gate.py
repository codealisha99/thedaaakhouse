"""Step 05: truthfulness gate + export reparse validation."""

from app.analysis.ats_v2 import analyze_ats_v2
from app.resume.pdf import render_resume_pdf, validate_pdf_export
from app.resume.validation import gate_edits, ensure_supported

MASTER = """Sam Lee
sam@example.com 555-0199

EXPERIENCE
Senior Backend Engineer, Beta Corp, 2020-2025
- Built RAG pipelines with Python and FastAPI serving 10k users
- Shipped Docker images to Kubernetes clusters
"""

JD = "Senior Backend Engineer. Requirements: 4+ years Python, Kubernetes, Rust, TensorFlow."


def gate(line):
    r = gate_edits(MASTER, [line])
    return "ACC" if r["accepted"] else "REJ"


def test_fabricated_metrics_rejected():
    assert gate("- Built RAG pipelines with FastAPI serving 50k users") == "REJ"
    assert gate("- Built RAG pipelines with FastAPI serving 10k users") == "ACC"
    assert gate("Improved latency by 30% with a new cache layer") == "REJ"


def test_fabricated_skills_rejected_alias_aware():
    assert gate("- Used PostgreSQL, Redis, and Kafka for data flows") == "REJ"
    # k8s -> Kubernetes alias switch is supported (canonical term occurs)
    assert gate("- Used k8s for deployments") == "ACC"
    # k9s is a different product and must not inherit Kubernetes' support
    assert gate("- Ran k9s against the cluster") == "REJ"


def test_fabricated_employers_and_identity_rejected():
    assert gate("- Engineered pipelines at Gamma Systems") == "REJ"
    assert gate("- Engineered pipelines at Beta Corp") == "ACC"
    assert gate("Sam Lee\nsam@example.com 555-0199") == "ACC"  # verbatim header


def test_supported_paraphrases_pass():
    # verb swaps and reordering never fabricate facts
    assert gate("Delivered RAG pipelines with Python and FastAPI serving 10k users") == "ACC"
    assert gate("- Ship Docker images to Kubernetes clusters") == "ACC"


def test_ats_v2_no_longer_aliases_fabricated_terms():
    # JD demands unsaliased terms: k9s/tf/gha no longer map to canonical matches
    r = analyze_ats_v2(
        "- Ran k9s tf and gha pipelines", "Requirements: Kubernetes, TensorFlow, GitHub Actions.")
    got = {e["requirement"].casefold() for e in r["matched"]}
    assert "kubernetes" not in got
    assert "tensorflow" not in got
    assert "github actions" not in got


def test_ats_v2_experience_from_date_ranges_not_fabricated():
    out = analyze_ats_v2(MASTER, JD)
    assert out["categories"]["experience"]["detail"].endswith("(from date ranges)")
    # resume evidence: 5y span + header line; JD 4 years -> satisfied
    assert 0 < out["categories"]["experience"]["score"] <= 100


def test_export_reparse_validation_catches_unreadable():
    content = "Built Python APIs with FastAPI"
    pdf = render_resume_pdf("Tailored", content)
    ok = validate_pdf_export(pdf, content)
    assert ok["readable"] is True and ok["line_coverage"] >= 0.7
    bad = validate_pdf_export(b"%PDF-1.4 garbage truncat", content)
    assert bad["readable"] is False and bad["error"]


def test_ensure_supported_raises():
    try:
        ensure_supported("- Deployed 42 services at Vega Corp", MASTER)
        raise AssertionError("should have raised")
    except ValueError as e:
        assert "truthfulness gate" in str(e)
