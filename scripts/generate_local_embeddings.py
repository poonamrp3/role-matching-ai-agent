#!/usr/bin/env python3
"""Generate local Nomic embedding vectors for Stage 2 retrieval documents.

This script does not create or query a vector database. It writes a portable NumPy
matrix plus a manifest so the next stage can load vectors into a chosen database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

# This project uses PyTorch. Disable an incompatible optional TensorFlow installation before
# sentence-transformers imports Transformers and probes available backends.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# Force rather than default: hosted shells sometimes inject a larger OpenMP setting which causes
# shared-memory initialization failures in this CPU-only environment.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import torch
from sentence_transformers import SentenceTransformer

# Qdrant indexing is an offline batch job; one CPU thread avoids OpenMP shared-memory failures
# in restricted execution environments and makes its memory profile predictable.
torch.set_num_threads(1)
torch.set_num_interop_threads(1)


MODEL_ID = "nomic-ai/nomic-embed-text-v1.5"
DOCUMENT_PREFIX = "search_document: "


def load_documents(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def count_tokens(model: SentenceTransformer, texts: list[str], document_ids: list[str]) -> tuple[int, list[str]]:
    """Return the longest input and document IDs that exceed the model sequence length."""
    lengths = [len(model.tokenizer(text, truncation=False)["input_ids"]) for text in texts]
    over_limit = [document_id for document_id, length in zip(document_ids, lengths, strict=True) if length > model.max_seq_length]
    return max(lengths, default=0), over_limit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/esco_retrieval_documents.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/embeddings"))
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--dimensions", type=int, default=512, choices=(64, 128, 256, 512, 768))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="cpu", choices=("cpu", "mps", "cuda"))
    parser.add_argument("--limit", type=int, default=None, help="Embed only the first N documents; useful for a smoke test.")
    args = parser.parse_args()

    documents = load_documents(args.input)
    if args.limit is not None:
        documents = documents[:args.limit]
    if not documents:
        raise ValueError("No retrieval documents were selected for embedding.")
    document_ids = [document["document_id"] for document in documents]
    texts = [DOCUMENT_PREFIX + document["embedding_text"] for document in documents]
    model = SentenceTransformer(args.model, device=args.device, trust_remote_code=True)
    max_token_count, over_limit = count_tokens(model, texts, document_ids)
    if over_limit:
        raise ValueError(
            f"{len(over_limit)} documents exceed model.max_seq_length={model.max_seq_length}. "
            "Revise chunking before generating embeddings."
        )

    # Follow Nomic's documented Matryoshka procedure: layer-norm → truncate → L2-normalize.
    raw_batches = []
    total_batches = (len(texts) + args.batch_size - 1) // args.batch_size
    for batch_number, start in enumerate(range(0, len(texts), args.batch_size), start=1):
        batch_texts = texts[start : start + args.batch_size]
        raw_batches.append(model.encode(
            batch_texts,
            batch_size=len(batch_texts),
            convert_to_numpy=True,
            # tqdm's progress-monitor thread cannot allocate shared memory in some restricted shells.
            show_progress_bar=False,
        ))
        print(f"Embedded batch {batch_number}/{total_batches} ({min(start + len(batch_texts), len(texts))}/{len(texts)} documents)")

    # Import NumPy after the PyTorch model has initialized. In this environment importing NumPy
    # first selects a conflicting OpenMP runtime for the encoder.
    import numpy as np
    raw_embeddings = np.concatenate(raw_batches, axis=0)

    # Equivalent NumPy implementation of Nomic's documented layer-norm → truncate → L2-normalize
    # sequence. Avoiding PyTorch's layer_norm keeps the CPU-only path compatible with restricted shells.
    mean = raw_embeddings.mean(axis=1, keepdims=True)
    variance = raw_embeddings.var(axis=1, keepdims=True)
    layer_normalized = (raw_embeddings - mean) / np.sqrt(variance + 1e-5)
    vectors = layer_normalized[:, :args.dimensions]
    vectors = vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
    vectors = vectors.astype(np.float32)
    if vectors.shape != (len(documents), args.dimensions):
        raise RuntimeError(f"Unexpected embedding matrix shape: {vectors.shape}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    vectors_path = args.output_dir / "esco_role_vectors.npz"
    manifest_path = args.output_dir / "esco_embedding_manifest.json"
    np.savez_compressed(vectors_path, document_ids=np.array(document_ids), vectors=vectors)
    manifest = {
        "source_retrieval_documents": str(args.input),
        "source_document_count": len(documents),
        "embedding_model": args.model,
        "model_revision": getattr(model[0].auto_model.config, "_commit_hash", None),
        "device": args.device,
        "batch_size": args.batch_size,
        "document_prefix": DOCUMENT_PREFIX.strip(),
        "dimensions": args.dimensions,
        "normalization": "layer_norm, truncate to dimensions, L2 normalize",
        "max_input_tokens": max_token_count,
        "model_max_sequence_length": model.max_seq_length,
        "vector_file": str(vectors_path),
        "vector_dtype": str(vectors.dtype),
        "vector_shape": list(vectors.shape),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_content_fingerprint": hashlib.sha256("".join(document["content_sha256"] for document in documents).encode()).hexdigest(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {vectors.shape[0]} x {vectors.shape[1]} vectors to {vectors_path}")
    print(f"Wrote embedding manifest to {manifest_path}")


if __name__ == "__main__":
    main()
