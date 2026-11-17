# Local Gemini Web2API setup

## Purpose

The query-processing prototype uses a local, OpenAI-compatible Gemini Web2API endpoint to turn a
recruiter's command into a structured request. It does not send Gmail message bodies, résumés,
attachments, OAuth credentials, or vector-store records to that endpoint.

## Configuration

The local Docker endpoint is configured outside the source code:

```text
GEMINI_BASE_URL=http://localhost:4981/v1
GEMINI_API_KEY=<local proxy key>
GEMINI_MODEL=gemini-3.5-flash
```

Copy `.env.example` to `.env`, enter the local proxy key, and keep that file private. `.env` is
already excluded from Git.

## Install and verify

```bash
python -m pip install -r requirements-stage6-query.txt
python scripts/check_local_llm.py
```

Expected output:

```text
connection-ok
```

## Design boundary

`src/role_matching/llm_client.py` is the only module that knows the provider URL, API key, model,
and timeout. Every workflow node imports `get_llm_client()` rather than creating its own
provider-specific client. This makes a later migration to an official provider an isolated
configuration change.
