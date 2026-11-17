"""Create concise, human-review-ready cards from deterministic retrieval results."""

from __future__ import annotations

import re
from typing import Any

from role_matching.workflows.schemas import ResponsePlan
from role_matching.workflows.state import RoleMatchingState


HUMAN_REVIEW_NOTE = (
    "These are semantic retrieval suggestions for human review, not hiring decisions or "
    "qualification probabilities."
)
MAX_DISPLAYED_ESSENTIAL_SKILLS = 5
APPLICATION_SUBJECT_PATTERN = re.compile(
    r"candidate\s+application\s*-\s*(?P<declared_role>.+?)\s*-\s*(?P<display_name>[^-]+?)\s*$",
    re.IGNORECASE,
)


def _candidate_profile(reference: dict[str, Any], extraction: dict[str, Any]) -> dict[str, Any]:
    """Return a short profile card without exposing the raw email or resumé text."""

    subject = str(reference.get("subject") or "")
    match = APPLICATION_SUBJECT_PATTERN.search(subject)
    return {
        "display_name": match.group("display_name").strip() if match else "Candidate submission",
        "declared_role": match.group("declared_role").strip() if match else None,
        "received_at": reference.get("received_at"),
        "attachment_count": extraction.get("attachment_count", 0),
    }


def result_formatting_node(state: RoleMatchingState) -> dict[str, Any]:
    """Format public ESCO metadata while omitting raw candidate email and resumé text."""

    plan = ResponsePlan.model_validate(
        state.get(
            "response_plan",
            {
                "candidate_fields": ["display_name", "declared_role", "received_at", "attachment_count"],
                "roles_to_show": 5,
                "description_max_chars": 500,
                "skills_per_role": 5,
                "include_similarity": False,
            },
        )
    )

    references_by_id = {
        reference["submission_id"]: reference for reference in state.get("submission_references", [])
    }
    extraction_by_id = {
        summary["submission_id"]: summary
        for summary in state.get("candidate_extraction_summary", [])
    }
    role_matches = state.get("role_matches", [])
    if not role_matches:
        return {
            "formatted_results": [],
            "workflow_events": [*state.get("workflow_events", []), "No role matches were available to format."],
        }

    cards: list[dict[str, Any]] = []
    for candidate_match in role_matches:
        submission_id = str(candidate_match["submission_id"])
        reference = references_by_id.get(submission_id, {})
        extraction = extraction_by_id.get(submission_id, {})
        roles = []
        for rank, role in enumerate(candidate_match.get("roles", [])[: plan.roles_to_show], start=1):
            rendered_role: dict[str, Any] = {"rank": rank, "title": role["title"]}
            if plan.include_similarity:
                rendered_role["semantic_similarity"] = round(float(role["cosine_similarity"]), 4)
            if plan.description_max_chars:
                description = str(role["description"])
                rendered_role["description"] = description[: plan.description_max_chars].rstrip()
                if len(description) > plan.description_max_chars:
                    rendered_role["description"] += "…"
            if plan.skills_per_role:
                rendered_role["essential_skills"] = role.get("essential_skills", [])[
                    : min(plan.skills_per_role, MAX_DISPLAYED_ESSENTIAL_SKILLS)
                ]
            roles.append(rendered_role)
        full_profile = _candidate_profile(reference, extraction)
        candidate_profile = {field: full_profile[field] for field in plan.candidate_fields}
        cards.append(
            {
                "candidate_submission": {
                    "submission_id": submission_id,
                    "received_at": reference.get("received_at"),
                    "subject": reference.get("subject"),
                },
                "candidate_profile": candidate_profile,
                "role_suggestions": roles,
                "human_review_note": HUMAN_REVIEW_NOTE,
            }
        )

    return {
        "formatted_results": cards,
        "workflow_events": [
            *state.get("workflow_events", []),
            f"Rendered field-level results for {len(cards)} candidate submission(s).",
        ],
    }
