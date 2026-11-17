"""A bounded Gmail implementation of the candidate-submission tool contract.

OAuth onboarding happens outside LangGraph. This module is deliberately limited to a configured
Gmail label and at most five messages per request; it is not a general mailbox-search tool.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from docx import Document
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pypdf import PdfReader

from role_matching.tools.candidate_submissions import (
    MAX_SUBMISSIONS_PER_REQUEST,
    CandidateText,
    SubmissionReference,
)


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
TOKEN_ENCRYPTION_KEY_ENV = "GMAIL_TOKEN_ENCRYPTION_KEY"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TOKEN_DB_PATH = PROJECT_ROOT / "data" / "runtime" / "gmail_tokens.db"
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
ALLOWED_ATTACHMENT_TYPES = {
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class GmailConnectionRequired(RuntimeError):
    """Raised when the user has not completed the separate Gmail connection step."""


@dataclass(frozen=True)
class GmailCredentialLoadResult:
    """In-memory credential result for a tool call; never serialize or log ``credentials``."""

    credentials: Credentials
    access_token_refreshed: bool


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


class GmailCredentialStore:
    """Store encrypted OAuth token JSON in a local SQLite database.

    The database contains ciphertext only. Its Fernet key is supplied separately through
    `GMAIL_TOKEN_ENCRYPTION_KEY` and is never written into this project or the database.
    """

    def __init__(
        self,
        connection_id: str = "demo-applications-mailbox",
        db_path: Path = DEFAULT_TOKEN_DB_PATH,
    ) -> None:
        if not connection_id.strip():
            raise ValueError("connection_id must be non-empty")
        self.connection_id = connection_id.strip()
        self.db_path = db_path
        self._cipher = Fernet(self._encryption_key())
        self._initialize_database()

    def connect(self, client_secrets_path: Path, timeout_seconds: int = 120) -> None:
        """Run one browser-based consent attempt and save its encrypted credential.

        A finite timeout means an abandoned consent tab cannot leave the local application in an
        apparently permanent "authorizing" state. A later recruiter request can safely start a
        fresh attempt.
        """

        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secrets_path),
            scopes=[GMAIL_READONLY_SCOPE],
        )
        credentials = flow.run_local_server(
            port=0,
            open_browser=True,
            authorization_prompt_message="Open this URL in a browser to connect Gmail: {url}",
            success_message="Gmail connected. You may close this browser tab.",
            timeout_seconds=timeout_seconds,
        )
        self._save(credentials)

    def has_stored_connection(self) -> bool:
        """Return whether this mailbox has a stored credential record.

        This deliberately checks only for the encrypted SQLite row. It does not decrypt,
        refresh, or expose OAuth credentials merely to render a UI status indicator.
        """

        with self._database() as database:
            row = database.execute(
                "SELECT 1 FROM gmail_tokens WHERE connection_id = ?",
                (self.connection_id,),
            ).fetchone()
        return row is not None

    def delete_connection(self) -> bool:
        """Remove the encrypted local credential record for this mailbox.

        Google consent is not revoked by this local operation; it removes the application's
        locally stored ability to use that consent. A subsequent workflow run must reconnect.
        """

        with self._database() as database:
            cursor = database.execute(
                "DELETE FROM gmail_tokens WHERE connection_id = ?",
                (self.connection_id,),
            )
        return cursor.rowcount > 0

    def load(self) -> Credentials:
        """Load valid credentials, refreshing and re-encrypting them if necessary."""

        return self.load_with_status().credentials

    def load_with_status(self) -> GmailCredentialLoadResult:
        """Load credentials and report only whether this call refreshed the access token."""

        with self._database() as database:
            row = database.execute(
                "SELECT encrypted_token FROM gmail_tokens WHERE connection_id = ?",
                (self.connection_id,),
            ).fetchone()
        if row is None:
            raise GmailConnectionRequired(
                "No Gmail connection is stored. Run scripts/connect_gmail.py first."
            )
        try:
            serialized = self._cipher.decrypt(row[0]).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise GmailConnectionRequired(
                "Stored Gmail credentials cannot be decrypted. Ensure the same "
                "GMAIL_TOKEN_ENCRYPTION_KEY is configured, or reconnect Gmail."
            ) from error
        credentials = Credentials.from_authorized_user_info(json.loads(serialized), [GMAIL_READONLY_SCOPE])
        access_token_refreshed = False
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save(credentials)
            access_token_refreshed = True
        if not credentials.valid:
            raise GmailConnectionRequired("Gmail connection is no longer valid. Reconnect Gmail.")
        return GmailCredentialLoadResult(
            credentials=credentials,
            access_token_refreshed=access_token_refreshed,
        )

    def _save(self, credentials: Credentials) -> None:
        encrypted_token = self._cipher.encrypt(credentials.to_json().encode("utf-8"))
        timestamp = int(time.time())
        with self._database() as database:
            database.execute(
                """
                INSERT INTO gmail_tokens (connection_id, encrypted_token, scopes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(connection_id) DO UPDATE SET
                    encrypted_token = excluded.encrypted_token,
                    scopes = excluded.scopes,
                    updated_at = excluded.updated_at
                """,
                (self.connection_id, encrypted_token, GMAIL_READONLY_SCOPE, timestamp, timestamp),
            )

    def _initialize_database(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._database() as database:
            database.execute("PRAGMA journal_mode = WAL")
            database.execute(
                """
                CREATE TABLE IF NOT EXISTS gmail_tokens (
                    connection_id TEXT PRIMARY KEY,
                    encrypted_token BLOB NOT NULL,
                    scopes TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

    def _database(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _encryption_key() -> bytes:
        key = os.environ.get(TOKEN_ENCRYPTION_KEY_ENV)
        if not key:
            raise RuntimeError(
                f"{TOKEN_ENCRYPTION_KEY_ENV} is required to encrypt the SQLite token store. "
                "Run scripts/generate_gmail_encryption_key.py and export the printed value."
            )
        try:
            Fernet(key.encode("utf-8"))
        except (TypeError, ValueError) as error:
            raise RuntimeError(f"{TOKEN_ENCRYPTION_KEY_ENV} is not a valid Fernet key") from error
        return key.encode("utf-8")


class GmailCandidateSubmissionTool:
    """Read candidate submissions only from one configured Gmail label."""

    def __init__(
        self,
        label: str,
        credential_store: GmailCredentialStore | None = None,
        connection_id: str = "demo-applications-mailbox",
    ) -> None:
        if not label.strip():
            raise ValueError("A dedicated candidate-submission label is required")
        self.label = label.strip()
        self.credential_store = credential_store or GmailCredentialStore(connection_id=connection_id)

    def fetch_latest_submissions(
        self,
        limit: int = MAX_SUBMISSIONS_PER_REQUEST,
        received_after: date | None = None,
        received_before: date | None = None,
        require_attachment: bool | None = None,
    ) -> list[SubmissionReference]:
        if not 1 <= limit <= MAX_SUBMISSIONS_PER_REQUEST:
            raise ValueError(f"limit must be between 1 and {MAX_SUBMISSIONS_PER_REQUEST}")
        service = self._service()
        # The label and filter grammar are constructed from validated fields; raw recruiter text
        # never becomes a Gmail query.
        query_terms = [f'label:"{self.label}"']
        if received_after:
            # Gmail's `after` is exclusive, so subtract one day for an inclusive date range.
            query_terms.append(f"after:{(received_after - timedelta(days=1)).strftime('%Y/%m/%d')}")
        if received_before:
            # Gmail's `before` is exclusive, so add one day for an inclusive date range.
            query_terms.append(f"before:{(received_before + timedelta(days=1)).strftime('%Y/%m/%d')}")
        if require_attachment is True:
            query_terms.append("has:attachment")
        elif require_attachment is False:
            query_terms.append("-has:attachment")
        response = service.users().messages().list(
            userId="me", q=" ".join(query_terms), maxResults=limit
        ).execute()
        references: list[SubmissionReference] = []
        for item in response.get("messages", []):
            message = service.users().messages().get(
                userId="me", id=item["id"], format="metadata", metadataHeaders=["Subject"]
            ).execute()
            headers = self._headers(message.get("payload", {}).get("headers", []))
            references.append(
                SubmissionReference(
                    submission_id=message["id"],
                    received_at=self._received_at(message),
                    subject=headers.get("subject", "(no subject)"),
                )
            )
        return sorted(references, key=lambda item: item.received_at, reverse=True)

    def extract_candidate_text(self, submission_id: str) -> CandidateText:
        service = self._service()
        message = service.users().messages().get(userId="me", id=submission_id, format="full").execute()
        body_sections: list[str] = []
        attachment_sections: list[str] = []
        for part in self._walk_parts(message.get("payload", {})):
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")
            body = part.get("body", {})
            if filename:
                extracted = self._extract_attachment(service, submission_id, filename, mime_type, body)
                if extracted:
                    attachment_sections.append(f"ATTACHMENT: {filename}\n{extracted}")
            elif mime_type in {"text/plain", "text/html"} and body.get("data"):
                text = self._decode_data(body["data"])
                if mime_type == "text/html":
                    parser = _HTMLTextExtractor()
                    parser.feed(text)
                    text = parser.text()
                if text.strip():
                    body_sections.append(text.strip())
        sections = []
        if body_sections:
            sections.append("EMAIL BODY:\n" + "\n".join(body_sections))
        sections.extend(attachment_sections)
        if not sections:
            raise ValueError(f"No supported candidate text found in Gmail message {submission_id}")
        return CandidateText(
            submission_id=submission_id,
            candidate_text="\n\n".join(sections),
            attachment_count=len(attachment_sections),
        )

    def _service(self) -> Any:
        return build("gmail", "v1", credentials=self.credential_store.load(), cache_discovery=False)

    def _extract_attachment(
        self, service: Any, message_id: str, filename: str, mime_type: str, body: dict[str, Any]
    ) -> str | None:
        if mime_type not in ALLOWED_ATTACHMENT_TYPES:
            return None
        if body.get("size", 0) > MAX_ATTACHMENT_BYTES:
            return None
        encoded = body.get("data")
        if not encoded and body.get("attachmentId"):
            response = service.users().messages().attachments().get(
                userId="me", messageId=message_id, id=body["attachmentId"]
            ).execute()
            encoded = response.get("data")
        if not encoded:
            return None
        content = base64.urlsafe_b64decode(encoded + "===")
        if mime_type == "text/plain":
            return content.decode("utf-8", errors="replace").strip()
        if mime_type == "application/pdf":
            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages).strip()
        return "\n".join(paragraph.text for paragraph in Document(io.BytesIO(content)).paragraphs).strip()

    @staticmethod
    def _walk_parts(part: dict[str, Any]):
        yield part
        for child in part.get("parts", []):
            yield from GmailCandidateSubmissionTool._walk_parts(child)

    @staticmethod
    def _headers(headers: list[dict[str, str]]) -> dict[str, str]:
        return {header.get("name", "").lower(): header.get("value", "") for header in headers}

    @staticmethod
    def _received_at(message: dict[str, Any]) -> str:
        milliseconds = int(message.get("internalDate", "0"))
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _decode_data(encoded: str) -> str:
        return base64.urlsafe_b64decode(encoded + "===").decode("utf-8", errors="replace")
