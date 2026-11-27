"""Regression checks for the full-text retrieval baseline."""
import unittest
from unittest.mock import patch

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from role_matching.tools.qdrant_role_search import QdrantRoleSearchTool, RoleSearchResult
from role_matching.workflows.nodes.role_retrieval import role_retrieval_node


class BaselineRetrievalTests(unittest.TestCase):
    def test_unique_active_roles_beyond_duplicate_point_pool(self):
        client = QdrantClient(":memory:")
        client.create_collection("roles", vectors_config=VectorParams(size=512, distance=Distance.COSINE))
        vector = [1.0] + [0.0] * 511
        points = [PointStruct(id=i, vector=vector, payload={
            "parent_role_id": "duplicate", "title": "Duplicate", "index_status": "active"
        }) for i in range(81)]
        points += [PointStruct(id=100 + i, vector=vector, payload={
            "parent_role_id": f"role-{i}", "title": f"Role {i}", "index_status": "active"
        }) for i in range(9)]
        points.append(PointStruct(id=200, vector=vector, payload={
            "parent_role_id": "inactive", "title": "Inactive", "index_status": "inactive"
        }))
        client.upsert("roles", points)
        with patch("role_matching.tools.qdrant_role_search.QdrantClient", return_value=client):
            results = QdrantRoleSearchTool(collection="roles").search_active_roles(vector, 10)
        self.assertEqual(len(results), 10)
        self.assertEqual(len({role.role_id for role in results}), 10)
        self.assertNotIn("inactive", {role.role_id for role in results})
        self.assertTrue(all(abs(role.cosine_similarity - 1.0) < 1e-6 for role in results))

    def test_baseline_retains_ten_but_downstream_receives_requested_count(self):
        roles = [RoleSearchResult(str(i), str(i), 1 - i / 100, "", [], []) for i in range(10)]
        state = {
            "match_request": {"candidate_limit": 1, "roles_per_candidate": 3,
                              "request_summary": "Match one candidate"},
            "candidate_vectors": [{"submission_id": "sample", "vector": [1.0]}],
        }
        with patch("role_matching.workflows.nodes.role_retrieval.QdrantRoleSearchTool") as tool:
            tool.return_value.search_active_roles.return_value = roles
            result = role_retrieval_node(state)
        self.assertEqual(tool.return_value.search_active_roles.call_args.kwargs["limit"], 10)
        self.assertEqual(len(result["baseline_role_matches"][0]["roles"]), 10)
        self.assertEqual(len(result["role_matches"][0]["roles"]), 3)
        self.assertEqual(result["baseline_role_matches"][0]["roles"][0]["cosine_similarity"], 1.0)


if __name__ == "__main__":
    unittest.main()
