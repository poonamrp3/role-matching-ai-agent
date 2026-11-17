#!/usr/bin/env python3
"""Make a non-sensitive connectivity check against the configured local LLM proxy."""

from __future__ import annotations

from role_matching.llm_client import LLMSettings, get_llm_client


def main() -> None:
    settings = LLMSettings.from_environment()
    client = get_llm_client(settings)
    response = client.chat.completions.create(
        model=settings.model,
        temperature=0,
        messages=[{"role": "user", "content": "Reply with exactly: connection-ok"}],
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
