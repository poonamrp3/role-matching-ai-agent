"""Local FastAPI boundary around the role-matching LangGraph.

This API intentionally returns only safe, recruiter-facing workflow output. Raw candidate text,
candidate vectors, Gmail OAuth material, and local database credentials never leave the backend.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from role_matching.tools.gmail_candidate_submissions import GmailCredentialStore
from role_matching.workflows.graph import build_role_matching_graph


load_dotenv()

app = FastAPI(title="RoleMatch AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class WorkflowRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    conversation_id: str = Field(min_length=1, max_length=100)


# Local, short-lived conversation state for the demo. Only already-safe, formatted role results
# are retained: never raw Gmail text, résumés, candidate vectors, or OAuth material.
_CONVERSATIONS: dict[str, dict[str, Any]] = {}

GMAIL_CONNECTION_ID_ENV = "GMAIL_CONNECTION_ID"
GMAIL_CLIENT_SECRETS_PATH_ENV = "GMAIL_OAUTH_CLIENT_SECRETS_PATH"
DEFAULT_GMAIL_CONNECTION_ID = "demo-applications-mailbox"
_gmail_connection_lock = threading.Lock()
_gmail_connection_job: dict[str, str | int | None] = {
    "status": "idle",
    "message": None,
    "attempt_id": 0,
}


def _gmail_store() -> GmailCredentialStore:
    return GmailCredentialStore(
        connection_id=os.getenv(GMAIL_CONNECTION_ID_ENV, DEFAULT_GMAIL_CONNECTION_ID)
    )


def _oauth_client_secrets_path() -> Path:
    configured_path = os.getenv(GMAIL_CLIENT_SECRETS_PATH_ENV, "").strip()
    if not configured_path:
        raise RuntimeError(
            f"{GMAIL_CLIENT_SECRETS_PATH_ENV} is not configured for this local API."
        )
    client_secrets_path = Path(configured_path).expanduser()
    if not client_secrets_path.is_file():
        raise RuntimeError("The configured local Google OAuth client file could not be found.")
    return client_secrets_path


def _run_gmail_connection(attempt_id: int) -> None:
    """Run Google consent outside the request thread and retain only status for the UI."""

    try:
        _gmail_store().connect(_oauth_client_secrets_path())
    except Exception:  # OAuth internals remain backend-only.
        with _gmail_connection_lock:
            if _gmail_connection_job["attempt_id"] != attempt_id:
                return
            _gmail_connection_job.update(
                status="failed",
                message=(
                    "The secure Gmail connection was not completed. Send your request again "
                    "when you are ready to reconnect."
                ),
            )
        return
    with _gmail_connection_lock:
        if _gmail_connection_job["attempt_id"] != attempt_id:
            return
        _gmail_connection_job.update(
            status="connected",
            message="Gmail was connected and the encrypted local credential was stored.",
        )


def _gmail_connection_status() -> dict[str, str | bool | None]:
    """Return safe connection state, never OAuth token data or client configuration."""

    try:
        connected = _gmail_store().has_stored_connection()
    except RuntimeError:
        return {
            "connected": False,
            "in_progress": False,
            "message": "Gmail connection setup is not available right now.",
        }
    if connected:
        return {
            "connected": True,
            "in_progress": False,
            "message": "Gmail is connected for this local session.",
        }
    with _gmail_connection_lock:
        job_status = _gmail_connection_job["status"]
        job_message = _gmail_connection_job["message"]
    return {
        "connected": connected,
        "in_progress": job_status == "in_progress",
        "message": job_message,
    }


def _begin_gmail_connection() -> dict[str, str | bool | None]:
    """Start browser consent when needed and return only recruiter-friendly state."""

    try:
        _oauth_client_secrets_path()
        store = _gmail_store()
    except RuntimeError:
        return {
            "connected": False,
            "in_progress": False,
            "message": (
                "I cannot start the secure Gmail connection right now. Please try the request "
                "again shortly."
            ),
        }

    if store.has_stored_connection():
        return {
            "connected": True,
            "in_progress": False,
            "message": "Gmail is already connected for this local session.",
        }

    with _gmail_connection_lock:
        # A recruiter may submit again after closing an unfinished consent tab. The new attempt
        # uses another loopback callback and supersedes its status; a stale attempt cannot later
        # overwrite the current status because it carries a different attempt identifier.
        attempt_id = int(_gmail_connection_job["attempt_id"] or 0) + 1
        _gmail_connection_job.update(status="in_progress", message=None, attempt_id=attempt_id)

    threading.Thread(
        target=_run_gmail_connection,
        args=(attempt_id,),
        name="gmail-oauth",
        daemon=True,
    ).start()
    return {
        "connected": False,
        "in_progress": True,
        "message": (
            "I opened a secure Google sign-in window for the applications mailbox. Complete "
            "authorization there, then send your request again."
        ),
    }


def _grounded_conversation_follow_up(
    prompt: str, conversation: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Answer narrowly supported, evidence-bounded follow-ups from safe conversation state.

    The current retrieval design matches a whole candidate document to a whole role document. It
    does *not* yet produce per-skill proof from a resumé. The response therefore exposes the
    top retrieved role's ESCO essential skills and makes that limitation explicit.
    """

    normalized = prompt.lower()
    summary_request = any(phrase in normalized for phrase in ("summarize", "summary", "what we did"))
    skills_request = "skill" in normalized
    if not summary_request and not skills_request:
        return None
    candidates = (conversation or {}).get("formatted_results", [])
    if not candidates:
        if summary_request:
            return {
                "status": "completed",
                "response_type": "conversation_summary",
                "assistant_message": (
                    "There is no completed candidate-matching result in this conversation yet. "
                    "Ask me to process candidate submissions first, and I can then summarise "
                    "the retrieved role suggestions."
                ),
                "formatted_results": [],
                "gmail_connection_ok": None,
                "validation_errors": [],
                "workflow_events": ["Returned a grounded empty-conversation summary; no tools were called."],
            }
        return None

    if summary_request:
        summaries = []
        for candidate in candidates:
            profile = candidate.get("candidate_profile", {})
            roles = candidate.get("role_suggestions", [])
            role_names = ", ".join(str(role.get("title", "role")) for role in roles[:3])
            summaries.append(
                f"{profile.get('display_name', 'Candidate submission')}: top suggestions were {role_names or 'unavailable'}."
            )
        return {
            "status": "completed",
            "response_type": "conversation_summary",
            "assistant_message": (
                f"So far, I processed {len(candidates)} candidate submission(s) and retrieved "
                "active ESCO role suggestions. " + " ".join(summaries)
            ),
            "formatted_results": [],
            "gmail_connection_ok": None,
            "validation_errors": [],
            "workflow_events": [
                "Answered a grounded summary request from the active local conversation.",
                "No additional Gmail or Qdrant retrieval was performed.",
            ],
        }

    candidate = candidates[0]
    roles = candidate.get("role_suggestions", [])
    if not roles:
        return None
    top_role = roles[0]
    profile = candidate.get("candidate_profile", {})
    candidate_name = profile.get("display_name", "the candidate")
    role_name = top_role.get("title", "the top suggested role")
    skills = top_role.get("essential_skills", [])
    if not skills:
        # Titles-only responses deliberately omit skills from the UI payload. The API retains
        # safe retrieved-role metadata for grounded skills follow-ups in the same conversation.
        detailed_matches = (conversation or {}).get("role_matches", [])
        if detailed_matches:
            skills = detailed_matches[0].get("roles", [{}])[0].get("essential_skills", [])
    return {
        "status": "completed",
        "response_type": "follow_up",
        "assistant_message": (
            f"For {candidate_name}, the top suggested role is {role_name}. "
            "Below are the ESCO essential skills associated with that role."
        ),
        "follow_up": {
            "candidate_name": candidate_name,
            "role_title": role_name,
            "essential_skills": skills,
            "evidence_note": (
                "This prototype made a role-level semantic retrieval match. These are role "
                "requirements, not individually verified skills from the candidate's resumé."
            ),
        },
        "formatted_results": [],
        "gmail_connection_ok": True,
        "validation_errors": [],
        "workflow_events": [
            "Answered a grounded skills follow-up from the active local conversation.",
            "No additional Gmail or Qdrant retrieval was performed.",
        ],
    }


def safe_workflow_response(result: dict[str, Any]) -> dict[str, Any]:
    """Select only API-safe fields from LangGraph state."""

    return {
        "status": result.get("status"),
        "response_type": result.get("response_type", "match_results"),
        "assistant_message": result.get("assistant_message"),
        "follow_up": result.get("follow_up"),
        "response_plan": result.get("response_plan"),
        "match_request": result.get("match_request"),
        "gmail_connection_ok": result.get("gmail_connection_ok"),
        "submission_references": result.get("submission_references", []),
        "candidate_extraction_summary": result.get("candidate_extraction_summary", []),
        "candidate_embedding_summary": result.get("candidate_embedding_summary", []),
        "formatted_results": result.get("formatted_results", []),
        "role_retrieval_errors": result.get("role_retrieval_errors", []),
        "validation_errors": result.get("validation_errors", []),
        "workflow_events": result.get("workflow_events", []),
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "RoleMatch AI local API"}


@app.get("/api/gmail/connection")
def gmail_connection_status() -> dict[str, str | bool | None]:
    """Report whether the local demo has an encrypted Gmail connection record."""

    return _gmail_connection_status()


@app.post("/api/gmail/connect")
def connect_gmail() -> dict[str, str | bool | None]:
    """Compatibility endpoint; normal recruiter requests start this flow automatically."""

    return _begin_gmail_connection()


@app.post("/api/run-workflow")
async def run_workflow(request: WorkflowRequest) -> dict[str, Any]:
    """Run one local demo workflow.

    This deliberately runs on the local server thread: the workflow makes controlled calls to
    localhost-only services (Gemini Web2API, Qdrant, and Gmail tooling) and the demo handles one
    recruiter request at a time.
    """

    follow_up = _grounded_conversation_follow_up(
        request.prompt.strip(), _CONVERSATIONS.get(request.conversation_id)
    )
    if follow_up:
        return safe_workflow_response(follow_up)

    graph = build_role_matching_graph()
    result = graph.invoke(
        {
            "raw_prompt": request.prompt.strip(),
            "status": "pending",
            "validation_errors": [],
            "workflow_events": [],
        }
    )
    response = safe_workflow_response(result)
    if response["response_type"] == "gmail_connection_required":
        connection = _begin_gmail_connection()
        response["assistant_message"] = str(connection["message"])
        response["gmail_connection_ok"] = False
        response["response_type"] = "gmail_connection_required"
    if response["formatted_results"]:
        _CONVERSATIONS[request.conversation_id] = {
            "formatted_results": response["formatted_results"],
            "role_matches": result.get("role_matches", []),
        }
    return response
