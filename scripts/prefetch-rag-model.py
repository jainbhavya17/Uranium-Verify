"""Explicit setup-only model download. Never receives case or document content."""

import os
from fastembed import TextEmbedding

model = TextEmbedding(
    "BAAI/bge-small-en-v1.5", cache_dir=os.getenv("RAG_MODEL_CACHE", "var/models"), threads=1
)
vector = next(model.embed(["Synthetic setup check: engineering classroom carpet area."]))
print("Local retrieval model ready; dimensions:", len(vector))
