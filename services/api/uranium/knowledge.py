"""Approved applicable passages only. Full-text fallback is labelled honestly."""

import hashlib
import os
import re
from functools import lru_cache
from sqlalchemy import select, text
from .models import GovernedVersion, KnowledgePassage


def applicable(scope, context):
    return (
        context["academic_year"] in scope["years"]
        and context["category"] in scope["categories"]
        and context["programme"] in scope["programmes"]
        and context["stage"] in scope["stages"]
        and scope["effective_from"] <= context["reference_date"] <= scope["effective_until"]
    )


@lru_cache(maxsize=1)
def embedding_model():
    # Never download a model during a user request. Setup prefetches the local cache.
    if os.getenv("RAG_EMBEDDINGS_ENABLED", "false") != "true":
        return None
    from fastembed import TextEmbedding

    return TextEmbedding(
        "BAAI/bge-small-en-v1.5",
        cache_dir=os.getenv("RAG_MODEL_CACHE", "var/models"),
        local_files_only=True,
        threads=1,
    )


def embed(value):
    try:
        model = embedding_model()
        return next(model.embed([value[:10000]])).tolist() if model else None
    except Exception:
        return None


def retrieve(db, p, query):
    context = query.model_dump(mode="json")
    # Access, editorial state and applicability are enforced before either ranking path.
    sources = db.scalars(
        select(GovernedVersion).where(GovernedVersion.kind == "SOURCE", GovernedVersion.status == "APPROVED")
    ).all()
    sources = {
        s.id: s
        for s in sources
        if p.roles.intersection(s.payload["scope"]["roles"]) and applicable(s.payload["scope"], context)
    }
    if not sources:
        return {
            "mode": "ABSTAIN",
            "answer": None,
            "citations": [],
            "reason": "No approved applicable source in your access scope.",
        }
    rows = db.scalars(select(KnowledgePassage).where(KnowledgePassage.source_id.in_(sources))).all()
    # Reindexing appends observations. Prefer the newest embedding-capable copy per source/checksum.
    dedup = {}
    for row in sorted(rows, key=lambda r: (r.embedding is not None, r.created_at, r.id)):
        dedup[(row.source_id, row.checksum)] = row
    rows = list(dedup.values())
    words = set(re.findall(r"\w+", query.query.casefold())) - {
        "the",
        "a",
        "an",
        "for",
        "is",
        "of",
        "and",
        "what",
        "how",
    }
    scores = {
        r.id: len(words.intersection(set(re.findall(r"\w+", r.text.casefold())))) / max(len(words), 1)
        for r in rows
    }
    mode = "KEYWORD_ONLY_FALLBACK"
    if db.bind.dialect.name == "postgresql" and rows:
        scored = db.execute(
            text(
                "SELECT id, ts_rank_cd(to_tsvector('english',text),to_tsquery('english',:q)) AS score FROM knowledge_passages WHERE source_id = ANY(:sources)"
            ),
            {
                "q": " | ".join(sorted(set(re.findall(r"[a-z0-9]+", query.query.casefold())))) or "unknown",
                "sources": list(sources),
            },
        ).all()
        scores = {
            identifier: float(score) for identifier, score in scored if identifier in {r.id for r in rows}
        }
        mode = "POSTGRES_FULLTEXT_ONLY"
        available = db.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')"))
        vector = embed(query.query) if available else None
        if vector is not None and any(r.embedding for r in rows):
            # Parameter-bound vectors; the eligible IDs are filtered before vector distance.
            for row in rows:
                if row.embedding and row.embedding_model == "BAAI/bge-small-en-v1.5":
                    distance = db.scalar(
                        text("SELECT CAST(:stored AS vector) <=> CAST(:query AS vector)"),
                        {"stored": str(row.embedding), "query": str(vector)},
                    )
                    scores[row.id] = scores.get(row.id, 0) + max(0, 1 - float(distance))
            mode = "HYBRID_POSTGRES_FTS_PGVECTOR_BGE_SMALL"
    ranked = sorted((r for r in rows if scores.get(r.id, 0) > 0), key=lambda r: (-scores[r.id], r.id))[:3]
    # Require explicit lexical grounding as well as any embedding similarity.
    ranked = [
        r
        for r in ranked
        if len(words.intersection(set(re.findall(r"\w+", r.text.casefold())))) >= min(2, len(words)) and words
    ]
    if not ranked:
        return {
            "mode": mode,
            "answer": None,
            "citations": [],
            "reason": "Grounding is weak; no cited answer was generated.",
        }
    citations = [
        {
            "id": r.id,
            "source_id": r.source_id,
            "source_version": sources[r.source_id].number,
            "clause": r.clause,
            "printed_page": r.printed_page,
            "pdf_page": r.pdf_page,
            "checksum": r.checksum,
            "source_url": sources[r.source_id].payload["source_url"],
            "excerpt": r.text,
            "interpretation": sources[r.source_id].payload["interpretation"],
        }
        for r in ranked
    ]
    return {
        "mode": mode,
        "answer": "\n".join(c["excerpt"] for c in citations),
        "citations": citations,
        "limitation": "Cited source excerpts only. Retrieval does not publish rules or determine compliance.",
    }


def index_source(db, source):
    payload = source.payload
    vector = embed(payload["text"])
    row = KnowledgePassage(
        source_id=source.id,
        checksum=hashlib.sha256(payload["text"].encode()).hexdigest(),
        clause=payload["clause"],
        printed_page=payload["printed_page"],
        pdf_page=payload["pdf_page"],
        text=payload["text"],
        embedding=vector,
        embedding_model="BAAI/bge-small-en-v1.5" if vector else None,
    )
    db.add(row)
