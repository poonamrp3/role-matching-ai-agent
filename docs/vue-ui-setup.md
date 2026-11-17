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
