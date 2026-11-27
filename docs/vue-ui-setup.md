# Local Vue UI

The interface is a local Vue application backed by FastAPI. It must run on the same Mac as the
local Gemini Web2API container, Gmail token store, and Qdrant database; it is not designed for
deployment to a public host.

## First-time setup

```bash
python -m pip install -r requirements-ui.txt
cd frontend
npm install
```

## Run the demo

Open two terminals.

Terminal 1 starts the protected Python API:

```bash
cd /Users/poonampawar/Documents/ChatGPT/CrowdDoing_Roles_Processing
python -m uvicorn role_matching.api.app:app --app-dir src --host 127.0.0.1 --port 8000
```

Terminal 2 starts the Vue interface:

```bash
cd /Users/poonampawar/Documents/ChatGPT/CrowdDoing_Roles_Processing/frontend
npm run dev
```

Open `http://127.0.0.1:5173` in your browser.

The Vue browser receives only safe output from FastAPI: request status, workflow events, Gmail
connection state, submission references, extraction and embedding summaries, and formatted ESCO
role cards. Candidate email text, attachment text, vectors, OAuth tokens, and SQLite contents
remain in the Python process.

Successful structured UI runs also write `structured-results.json` in the
project's `output/` directory. The file contains submission IDs and
retrieved ESCO roles, not candidate document text or vectors, and can be used as the structured
input to `scripts/compare_retrieval_results.py`. The output directory is ignored by Git. No file
is written for follow-ups, failed profile extraction, or a run without structured role results.
Each successful structured UI run replaces that file. The UI's comparison button opens the HTML
report using `output/baseline-results.json` and the latest structured results. It checks that the
submission IDs match and reports an error if they do not. Each click also saves or replaces
`output/retrieval-comparison.html` and opens that styled report in a new browser tab.
