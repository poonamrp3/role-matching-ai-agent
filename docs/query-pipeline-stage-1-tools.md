# Query pipeline, step 1 — Candidate-submission tool

## Purpose

Before Gmail authentication or an LLM, the system needs a small, controlled boundary for
candidate-submission data. LangGraph calls this boundary; it does not call a mailbox provider
directly.

## Tool contract

`CandidateSubmissionTool` has exactly two operations:

1. `fetch_latest_submissions(limit)` returns a maximum of five newest submission references. A
   reference contains only the ID, received time, and subject—not the raw résumé.
2. `extract_candidate_text(submission_id)` returns labelled email-body and attachment text for
   one already-approved submission.

The hard limit and separation between listing and reading make data scope visible and testable.

## Current implementation

`LocalCandidateSubmissionTool` reads five clearly labelled, fictional submissions from
`data/demo/synthetic_candidate_submissions.json`. They are not candidates, emails, or data from
CrowdDoing. This validates the tool and later the graph without personal data or OAuth setup.

Run it with:

```bash
cd /Users/poonampawar/Documents/ChatGPT/CrowdDoing_Roles_Processing
python scripts/demo_candidate_submission_tool.py
```

## Gmail later

A future `GmailCandidateSubmissionTool` will implement the same two methods using the Google
Gmail API and OAuth 2.0 authorization-code flow. A separate web/API route initiates consent and
handles the callback. The LangGraph run only checks that a connection exists and calls the
bounded tool. Tokens must never be placed in graph state, prompts, source control, or logs.

Google Drive is not needed for the core demonstration. It introduces another OAuth scope without
representing the actual candidate-submission source.

## Interview explanation

> “I put mailbox access behind a provider-independent tool contract. I first validated the
> workflow with synthetic submissions, then a Gmail adapter can replace the local adapter without
> changing the graph. The tool enforces a maximum retrieval scope and separates listing references
> from extracting approved content, supporting privacy and auditability.”
