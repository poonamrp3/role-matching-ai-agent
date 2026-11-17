# Gmail retrieval node

`workflows/nodes/gmail_retrieval.py` is the second Gmail-related node. It runs only after a valid
`MatchRequest` and successful `gmail_connection` check.

For this first version, it constructs `GmailCandidateSubmissionTool` with the fixed
`GMAIL_SUBMISSIONS_LABEL` value (`CandidateSubmissions` by default) and retrieves no more than the
validated `candidate_limit`, which is capped at five.

Its state output contains only submission references:

- Gmail message ID;
- received time; and
- subject.

It does not read email bodies or attachments. Date and attachment filters are deliberately
rejected rather than silently ignored; they will be implemented with a future filter-aware version
of this same bounded tool.
