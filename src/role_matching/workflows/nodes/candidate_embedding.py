"""Create local Nomic query vectors from extracted candidate text."""

from __future__ import annotations

from typing import Any

from role_matching.nomic_embeddings import NomicEmbeddingService
from role_matching.workflows.state import RoleMatchingState


def candidate_embedding_node(state: RoleMatchingState) -> dict[str, Any]:
    """Embed candidate text locally; raw text never leaves the MacBook through this node."""

    documents = state.get("candidate_documents", [])
    if not documents:
        return {
            "status": "failed",
            "candidate_vectors": [],
            "candidate_embedding_summary": [],
            "validation_errors": [
                *state.get("validation_errors", []),
                "No extracted candidate text is available for embedding.",
            ],
            "workflow_events": [*state.get("workflow_events", []), "Candidate embedding was not started."],
        }

    service = NomicEmbeddingService()
    vectors: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for document in documents:
        submission_id = str(document["submission_id"])
        try:
            embedding = service.embed_query(str(document["candidate_text"]))
            vectors.append(
                {
                    "submission_id": submission_id,
                    "vector": embedding.vector.tolist(),
                }
            )
            summaries.append(
                {
                    "submission_id": submission_id,
                    "vector_dimensions": len(embedding.vector),
                    "vector_norm": round(float((embedding.vector**2).sum() ** 0.5), 6),
                    "input_token_count": embedding.token_count,
                    "embedding_status": "completed",
                }
            )
        except Exception as error:
            errors.append({"submission_id": submission_id, "error": str(error)})

    if not vectors:
        return {
            "status": "failed",
            "candidate_vectors": [],
            "candidate_embedding_summary": summaries,
            "candidate_embedding_errors": errors,
            "validation_errors": [
                *state.get("validation_errors", []),
                "No candidate query vectors could be created.",
            ],
            "workflow_events": [*state.get("workflow_events", []), "Candidate embedding failed."],
        }

    return {
        "candidate_vectors": vectors,
        "candidate_embedding_summary": summaries,
        "candidate_embedding_errors": errors,
        "workflow_events": [
            *state.get("workflow_events", []),
            f"Created local Nomic query vector(s) for {len(vectors)} candidate(s).",
        ],
    }
