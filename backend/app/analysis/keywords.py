"""Keyword + requirement extraction from job descriptions. Deterministic.

No LLM, no invention: every term returned provably occurs in the source text.
"""

import re
from collections import Counter

STOPWORDS = frozenset(
    """a an the and or of to in for on with as at by from is are was were be been
    being will would should could can may might must shall do does did done have has had
    having we you they he she it our your their his her its this that these those then
    than so such no not only also just about into over after before between through during
    each other more most some any all both few many much own same too very new ideal
    strong proven ability work working join team help including include includes join us
    looking seek seeking build building fast growing dynamic passionate talented world
    class best great excellent opportunity opportunities benefits offer offers role you
    your youre plus per within without across ensure drive driving passionate compensation
    competitive comprehensive medical dental vision pto remote hybrid onsite who what
    when where which while""".split()
)

# Curated technology/skill lexicon. A term is only reported as a "skill" if it
# literally appears in the JD — the lexicon ranks, never invents.
TECH_LEXICON = frozenset(
    """python java typescript javascript go rust c++ c# sql react next.js vue angular
    node.js nodejs fastapi django flask spring spring-boot .net pytorch tensorflow keras
    scikit-learn pandas numpy llm gpt rag langchain vector pgvector pinecone weaviate
    faiss embeddings fine-tuning prompt-engineering agents mcp docker kubernetes aws gcp
    azure terraform linux ci/cd git github gitlab jenkins kafka spark airflow hadoop
    elasticsearch redis postgres postgresql mysql mongodb graphql rest api microservices
    system-design distributed-systems machine-learning deep-learning nlp computer-vision
    data-science statistics a/b-testing etl dbt snowflake bigquery redshift figma agile
    scrum jira excelSheets sheets crm salesforce hubspot seo sem ga4 analytics amplitude
    mixpanel tableau powerbi looker machine learning data structures algorithms oop
    restful oauth jwt testing pytest jest selenium cypress playwright tdd linux bash shell
    networking http tcp dns cdn load-balancing caching auth authentication authorization
    encryption rbac iam monitoring prometheus grafana datadog new-relic pagerduty incident
    on-call mlops kubeflow sagemaker vertex-ai azure-ml huggingface openai anthropic gemini
    llama mistral ollama vllm triton tensorrt onnx quantization pruning distillation evals
    ragas guardrails bedrock copilot cursor windsurf v0 lovable replit figma-make framer
    webflow wordpress shopify stripe plaid twilio sendgrid algolia meilisearch typesense
    clickhouse duckdb polars rust wasm electron react-native flutter swift kotlin android
    ios expo firebase supabase vercel netlify cloudflare render railway fly.io heroku
    digitalocean""".split()
)

_TOKEN_RE = re.compile(r"[a-z][a-z0-9+#.\-/]*")
_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)")


def tokenize(text: str) -> list[str]:
    toks = [t.strip(".-/") for t in _TOKEN_RE.findall((text or "").lower())]
    return [t for t in toks if len(t) > 1 and t not in STOPWORDS]


def extract_keywords(text: str, top_n: int = 40) -> list[dict]:
    """Ranked keywords actually present in the text (count × lexicon boost)."""
    toks = tokenize(text)
    counts = Counter(toks)
    scored = [
        {"term": t, "count": c, "weight": round(c * (2.0 if t in TECH_LEXICON else 1.0), 2)}
        for t, c in counts.items()
    ]
    scored.sort(key=lambda d: (-d["weight"], -d["count"], d["term"]))
    return scored[:top_n]


def extract_bigrams(text: str, top_n: int = 15) -> list[str]:
    toks = tokenize(text)
    pairs = Counter(zip(toks, toks[1:]))
    return [" ".join(p) for p, c in pairs.most_common(top_n) if c >= 2]


def extract_skills(text: str) -> list[str]:
    """Skills = lexicon terms literally present in the JD, most frequent first."""
    counts = Counter(t for t in tokenize(text) if t in TECH_LEXICON)
    return [t for t, _ in counts.most_common()]


def extract_responsibilities(text: str, max_items: int = 12) -> list[str]:
    items: list[str] = []
    for line in (text or "").splitlines():
        s = line.strip().lstrip("-•*·0123456789. ").strip()
        if len(s) > 25 and any(s.lower().startswith(v) for v in (
            "build", "design", "develop", "lead", "own", "drive", "partner",
            "collaborate", "implement", "maintain", "improve", "launch", "define",
            "analyze", "manage", "mentor", "architect", "ship", "scale", "write",
            "create", "deliver", "support", "troubleshoot", "optimize", "you will",
            "responsible",
        )):
            items.append(s[:300])
        if len(items) >= max_items:
            break
    return items


def extract_experience_years(text: str) -> int | None:
    found = [int(m.group(1)) for m in _YEARS_RE.finditer(text or "")]
    return max(found) if found else None


def analyze_jd(raw_text: str) -> dict:
    """Full deterministic JD breakdown. Empty text → ValueError (never fake it)."""
    from app.ingestion.jd_parser import clean_text

    cleaned = clean_text(raw_text).text
    if not cleaned.strip():
        raise ValueError("job description text is empty")
    keywords = extract_keywords(cleaned)
    return {
        "keywords": keywords,
        "phrases": extract_bigrams(cleaned),
        "skills": extract_skills(cleaned),
        "responsibilities": extract_responsibilities(cleaned),
        "experience_years": extract_experience_years(cleaned),
        "word_count": len(cleaned.split()),
    }
