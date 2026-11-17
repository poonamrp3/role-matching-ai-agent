"""Shared local Nomic embedding service for ESCO retrieval workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# Configure optional ML backends before importing sentence-transformers.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import torch
from sentence_transformers import SentenceTransformer


NOMIC_MODEL_ID = "nomic-ai/nomic-embed-text-v1.5"
QUERY_PREFIX = "search_query: "
EMBEDDING_DIMENSIONS = 512

torch.set_num_threads(1)
torch.set_num_interop_threads(1)


@dataclass(frozen=True)
class QueryEmbedding:
    """One in-memory query vector and safe metadata about its construction."""

    vector: Any
    token_count: int


class NomicEmbeddingService:
    """Create Matryoshka-compatible query embeddings for the existing ESCO role index."""

    def __init__(
        self,
        model_id: str = NOMIC_MODEL_ID,
        dimensions: int = EMBEDDING_DIMENSIONS,
        device: str = "cpu",
    ) -> None:
        if dimensions not in {64, 128, 256, 512, 768}:
            raise ValueError("dimensions must be one of 64, 128, 256, 512, or 768")
        self.dimensions = dimensions
        self.model = SentenceTransformer(model_id, device=device, trust_remote_code=True)

    def embed_query(self, text: str) -> QueryEmbedding:
        """Embed one candidate retrieval text using Nomic's query-side Matryoshka procedure."""

        import numpy as np

        if not text.strip():
            raise ValueError("Candidate retrieval text is empty.")
        prefixed_text = QUERY_PREFIX + text.strip()
        token_count = len(self.model.tokenizer(prefixed_text, truncation=False)["input_ids"])
        if token_count > self.model.max_seq_length:
            raise ValueError(
                f"Candidate text has {token_count} tokens, exceeding the model limit "
                f"of {self.model.max_seq_length}. It must be chunked before embedding."
            )

        raw_vector = self.model.encode(
            [prefixed_text],
            batch_size=1,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        # Same Nomic Matryoshka procedure used when indexing ESCO role documents.
        mean = raw_vector.mean()
        variance = raw_vector.var()
        layer_normalized = (raw_vector - mean) / np.sqrt(variance + 1e-5)
        vector = layer_normalized[: self.dimensions]
        vector = vector / max(float(np.linalg.norm(vector)), 1e-12)
        vector = vector.astype(np.float32)
        if vector.shape != (self.dimensions,):
            raise RuntimeError(f"Unexpected query-vector shape: {vector.shape}")
        return QueryEmbedding(vector=vector, token_count=token_count)
