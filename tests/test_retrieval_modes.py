import unittest
from unittest.mock import patch
import numpy as np

from role_matching.workflows.graph import _route_after_candidate_extraction
from role_matching.workflows.nodes.candidate_embedding import candidate_embedding_node


class RetrievalModeTests(unittest.TestCase):
    def test_baseline_bypasses_profile(self):
        state = {"retrieval_mode": "baseline", "candidate_documents": [
            {"submission_id": "test", "candidate_text": "full text"}]}
        self.assertEqual(_route_after_candidate_extraction(state), "candidate_embedding")
        with patch("role_matching.workflows.nodes.candidate_embedding.NomicEmbeddingService") as service:
            service.return_value.embed_query.return_value.vector = np.array([1.0])
            service.return_value.embed_query.return_value.token_count = 2
            result = candidate_embedding_node(state)
        service.return_value.embed_query.assert_called_once_with("full text")
        self.assertEqual(result["candidate_embedding_summary"][0]["query_type"], "full_text")

    def test_structured_routes_through_profile(self):
        self.assertEqual(_route_after_candidate_extraction({
            "retrieval_mode": "structured", "candidate_documents": [{}]}), "candidate_profile")


if __name__ == "__main__":
    unittest.main()
