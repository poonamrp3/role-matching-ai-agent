"""One development-only local LLM client shared by workflow nodes.

Only recruiter commands should be sent through this client at this stage.  Gmail message bodies,
résumés, attachments, OAuth tokens, and Qdrant payloads remain inside the application.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


@dataclass(frozen=True)
class LLMSettings:
    """Configuration for an OpenAI-compatible local LLM endpoint."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 180.0

    @classmethod
    def from_environment(cls) -> "LLMSettings":
        missing = [
            name
            for name in ("GEMINI_BASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL")
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                "Missing local LLM configuration: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and configure it locally."
            )
        return cls(
            base_url=os.environ["GEMINI_BASE_URL"],
            api_key=os.environ["GEMINI_API_KEY"],
            model=os.environ["GEMINI_MODEL"],
        )


def get_llm_client(settings: LLMSettings | None = None) -> OpenAI:
    """Create a client for the configured local proxy without exposing its key elsewhere."""

    resolved = settings or LLMSettings.from_environment()
    return OpenAI(
        base_url=resolved.base_url,
        api_key=resolved.api_key,
        timeout=resolved.timeout_seconds,
    )
