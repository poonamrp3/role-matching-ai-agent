# Gmail connection node

`workflows/nodes/gmail_connection.py` is the first Gmail-related LangGraph node. It runs only
after query processing has produced a validated `MatchRequest`.

It uses `GmailCredentialStore.load_with_status()` to:

1. read the encrypted OAuth token blob from local SQLite;
2. decrypt it in process memory using `GMAIL_TOKEN_ENCRYPTION_KEY`;
3. ask Google to refresh the access token only when it is expired;
4. write a newly refreshed credential blob back to SQLite in encrypted form; and
5. add only safe readiness metadata to LangGraph state.

The node does not list Gmail messages, access the `CandidateSubmission` label, include tokens in
state, or send OAuth data to the local LLM.
