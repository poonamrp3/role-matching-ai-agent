"""Tests for structured candidate profile validation and workflow behavior."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from role_matching.workflows.nodes.candidate_profile import (
    CandidateProfile, candidate_profile_node, profile_query,
)


class CandidateProfileTests(unittest.TestCase):
    def test_schema_and_query(self):
        profile = CandidateProfile.model_validate({
            "skills": [{"value": "Python", "evidence": "Python programming"}],
            "experience": [{"value": "Data pipelines", "evidence": "built data pipelines"}],
        })
        self.assertEqual(profile_query(profile), "Skills: Python\nExperience: Data pipelines")
        with self.assertRaises(ValidationError):
            CandidateProfile.model_validate({"skills": [], "experience": [], "name": "someone"})

    def test_rejects_evidence_not_in_source_and_hides_response(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "skills": [{"value": "Python", "evidence": "not present"}], "experience": []
        })))])
        with patch("role_matching.workflows.nodes.candidate_profile.LLMSettings.from_environment") as settings, \
             patch("role_matching.workflows.nodes.candidate_profile.get_llm_client") as client:
            settings.return_value.model = "test"
            client.return_value.chat.completions.create.return_value = response
            result = candidate_profile_node({"candidate_documents": [{"submission_id": "1", "candidate_text": "Python"}]})
        self.assertEqual(result["candidate_profiles"], [])
        self.assertEqual(result["candidate_profile_errors"][0]["error"], "Structured profile extraction failed.")

    def test_accepts_grounded_quote(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "skills": [{"value": "Python", "evidence": "Python programming"}], "experience": []
        })))])
        with patch("role_matching.workflows.nodes.candidate_profile.LLMSettings.from_environment") as settings, \
             patch("role_matching.workflows.nodes.candidate_profile.get_llm_client") as client:
            settings.return_value.model = "test"
            client.return_value.chat.completions.create.return_value = response
            result = candidate_profile_node({"candidate_documents": [{"submission_id": "1", "candidate_text": "Python programming"}]})
        self.assertEqual(result["candidate_profiles"][0]["profile"]["skills"][0]["value"], "Python")


if __name__ == "__main__":
    unittest.main()
