# Gmail candidate-submission tool — setup and security boundary

## What belongs where

Gmail connection is **onboarding**, not a role-matching graph node:

```text
One-time connection: browser consent → OAuth callback → encrypted token in SQLite
Each graph run: bounded Gmail tool → extract approved candidate text → profile/matching workflow
```

OAuth proves that a user authorised the application. It does not by itself limit the data to a
label. The `gmail.readonly` scope allows the application to read the connected account's mail;
the fixed label, five-message maximum, supported attachment types, and audit events are enforced
by this application's code. For a credible demo, use a dedicated test Gmail account or an
applications-only mailbox—not a personal mailbox.

## One-time Google Cloud configuration

1. Create a Google Cloud project and enable the Gmail API.
2. Configure the OAuth consent screen and add your Gmail account as a test user if the app is in
   testing mode.
3. Create an OAuth **Desktop app** client and download its client-secret JSON. Do not copy it into
   this repository or commit it.
4. Install the adapter dependencies:

   ```bash
   cd /Users/poonampawar/Documents/ChatGPT/CrowdDoing_Roles_Processing
   pip install -r requirements-stage5-gmail.txt
   ```

5. Generate an encryption key. Store this value in a password manager or secure local secret
   manager; it must be available in every terminal that runs the Gmail tool, but must not be put
   into Git or the SQLite database:

   ```bash
   python scripts/generate_gmail_encryption_key.py
   # Copy and run the export command it prints.
   ```

6. Create a Gmail label such as `CandidateSubmissions` in a dedicated test account and add up to
   candidate-submission messages with `.txt`, `.pdf`, or `.docx` résumés.
7. For prompt-triggered Gmail authorization, add the downloaded OAuth client path to the uncommitted local
   `.env` file:

   ```ini
   GMAIL_OAUTH_CLIENT_SECRETS_PATH=/absolute/path/to/client_secret.json
   ```

   The first candidate-processing request opens Google consent in the browser when no valid local
   Gmail connection exists. The resulting encrypted credential is saved to SQLite. The terminal
   route remains available for debugging:

   ```bash
   python scripts/connect_gmail.py --client-secrets /absolute/path/to/client_secret.json
   ```

   A browser opens for Google consent. The resulting access/refresh-token JSON is encrypted with
   the environment-supplied Fernet key and stored as ciphertext in
   `data/runtime/gmail_tokens.db`; no plaintext token file is written to the project.

8. The workflow calls `GmailCandidateSubmissionTool` with this label and a maximum of five
   messages. It does not accept an arbitrary Gmail search query from a user prompt.

## Current guardrails

- Read-only Gmail scope; no send, archive, delete, or label-modification permission.
- A fixed label supplied at tool construction—not a natural-language prompt converted into a Gmail query.
- A maximum of five messages per run.
- Only text, PDF, and DOCX attachments up to 5 MB are extracted.
- OAuth tokens are not graph state, prompts, source files, or logs. SQLite holds ciphertext only;
  the decryption key is separate from the database.

## Honest demo language

> “I separated connection onboarding from role matching. OAuth gives the application delegated,
> read-only mailbox access; the application tool then enforces the narrower business policy—a
> dedicated submissions label, five-message maximum, allowed attachment types, and no write
> operations. For the prototype I use a dedicated test mailbox, rather than connecting a personal
> inbox.”
