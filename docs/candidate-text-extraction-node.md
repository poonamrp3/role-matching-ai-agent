# Candidate-text extraction node

`workflows/nodes/candidate_text_extraction.py` receives only the submission references from the
same graph invocation. For each one, it uses the bounded Gmail tool to extract email-body text and
supported PDF, DOCX, or plain-text attachment content.

The Gmail adapter already enforces attachment type and size limits. Raw text is retained only in
the in-memory `candidate_documents` state field for the immediate next local node; no LangGraph
checkpointer is configured, and the terminal runner deliberately omits that field. Terminal output
shows only submission ID, attachment count, extracted character count, and extraction status.

The next node will consume that in-memory text to create local Nomic query embeddings.
