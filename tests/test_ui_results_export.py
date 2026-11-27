import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from role_matching.api.app import comparison_report, save_structured_results


class UiResultsExportTests(unittest.TestCase):
    def test_saves_comparison_data_without_candidate_text(self):
        result = {"candidate_documents": [{"candidate_text": "private résumé"}],
                  "structured_role_matches": [{"submission_id": "sample", "roles": [{
                      "role_id": "role-1", "title": "Electrician", "cosine_similarity": 0.8,
                      "candidate_text": "private résumé"}]}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(save_structured_results(result, Path(directory)))
            saved = json.loads(path.read_text())
            self.assertEqual(saved["structured_role_matches"][0]["roles"][0]["role_id"], "role-1")
            self.assertNotIn("private résumé", path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path, Path(save_structured_results(result, Path(directory))))

    def test_no_file_for_missing_results(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(save_structured_results({}, Path(directory)))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_comparison_requires_same_submission(self):
        role = {"role_id": "role-1", "title": "Electrician", "cosine_similarity": 0.8}
        baseline = {"baseline_role_matches": [{"submission_id": "sample", "roles": [role]}]}
        structured = {"structured_role_matches": [{"submission_id": "sample", "roles": [role]}]}
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            (output_dir / "baseline-results.json").write_text(json.dumps(baseline))
            (output_dir / "structured-results.json").write_text(json.dumps(structured))
            with patch("role_matching.api.app.OUTPUT_DIR", output_dir):
                response = comparison_report()
                self.assertIn(b"Electrician", response.body)
                self.assertEqual((output_dir / "retrieval-comparison.html").read_bytes(), response.body)
                baseline["baseline_role_matches"][0]["submission_id"] = "different"
                (output_dir / "baseline-results.json").write_text(json.dumps(baseline))
                with self.assertRaises(HTTPException) as error:
                    comparison_report()
                self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
