"""Tests for structured candidate profile validation and workflow behavior."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from role_matching.workflows.nodes.candidate_profile import (
    CandidateProfile, candidate_profile_node, profile_query,
)


class CandidateProfileTests(unittest.TestCase):
    def test_rejects_invalid_profile(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "skills": "Python", "experience": []
        })))])
        with patch("role_matching.workflows.nodes.candidate_profile.LLMSettings.from_environment") as settings, \
             patch("role_matching.workflows.nodes.candidate_profile.get_llm_client") as client:
            settings.return_value.model = "test"
            client.return_value.chat.completions.create.return_value = response
            result = candidate_profile_node({"candidate_documents": [{"submission_id": "1", "candidate_text": "Python"}]})
        self.assertEqual(result["candidate_profiles"], [])
        self.assertEqual(result["candidate_profile_errors"][0]["error"], "Structured profile extraction failed.")

    def test_builds_query_from_valid_profile(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "skills": ["Python"], "experience": ["Built data pipelines"]
        })))])
        with patch("role_matching.workflows.nodes.candidate_profile.LLMSettings.from_environment") as settings, \
             patch("role_matching.workflows.nodes.candidate_profile.get_llm_client") as client:
            settings.return_value.model = "test"
            client.return_value.chat.completions.create.return_value = response
            result = candidate_profile_node({"candidate_documents": [{"submission_id": "1", "candidate_text": "Python programming; built data pipelines"}]})
        profile = CandidateProfile.model_validate(result["candidate_profiles"][0]["profile"])
        self.assertEqual(profile.skills[0], "Python")
        self.assertEqual(profile_query(profile), "Skills: Python\nExperience: Built data pipelines")


if __name__ == "__main__":
    unittest.main()
