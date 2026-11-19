# JobFit AI

**See how well your resume fits a job, what is missing, and how to fix it, with the exact line from your resume as proof.**

JobFit AI is a RAG + agent application. It reads a resume and a job ad, finds evidence for every requirement with vector search, scores the fit, and coaches the candidate. An agent mode answers free questions by choosing its own tools, and an MCP server lets AI assistants such as Claude use JobFit as a tool.

![Fit report](docs/screenshots/report.png)

## Features

- **Fit report**: score, every requirement marked matched / partly / missing, with a highlighted quote from the resume as evidence
- **Sharper resume lines** rewritten for the job (no invented facts) and **likely interview questions** with answer tips
- **Agent mode**: ask anything ("Which skills am I missing?"); the agent picks tools, the UI shows each step live, and answers cite their sources like `[R3]`
- **MCP server**: the same tools exposed over the Model Context Protocol, so Claude Desktop can call them
- **Any file**: PDF, Word (DOCX), photos (PNG, JPG, WEBP) and TXT. Scanned PDFs and photos are read with Tesseract OCR
- **Demo mode**: works with no API key (rule-based), so anyone can try it
- **Quality checks in CI**: tests plus an AI evaluation that fails the pipeline if accuracy drops

## Architecture

```
            ┌──────────── docker compose ────────────┐
 Browser ──▶│ web (React + nginx) ──▶ api (FastAPI)  │──▶ Groq LLM (GPT-OSS 120B)
            │                          │   ▲         │
 Claude  ──▶│ mcp (MCP server) ────────┘   │         │
            │                     db (Postgres + pgvector)
            └────────────────────────────────────────┘
```

| Part | Tech | Job |
|---|---|---|
| `frontend/` | React, Vite, nginx | 5 screens; streams agent steps over Server-Sent Events |
| `backend/app/ingest.py` | pypdf, Tesseract OCR, python-docx | reads PDF, Word and images (OCR for scans), splits text into labelled chunks (R1, R2… / J1, J2…) |
| `backend/app/embeddings.py` | fastembed (bge-small, local) | turns chunks into 384-dim vectors, no API key |
| `backend/app/retrieval.py` | pgvector | cosine-similarity search |
| `backend/app/analysis.py` | LLM + Python | requirements → evidence → judge → **score in plain Python** → coaching |
| `backend/app/agent.py` | LLM tool calling | tool loop (max 6 steps) streaming each step |
| `backend/app/mcp_server.py` | MCP Python SDK | `list_documents`, `add_document`, `analyze_fit`, `search_documents`, `ask_jobfit` |
| `backend/evals/` | golden set | measures requirement recall and status accuracy |
| `.github/workflows/ci.yml` | GitHub Actions | lint → tests → eval → build & publish Docker images |

### How a fit report is made

1. **Requirements**: the LLM reads the job ad (as labelled chunks) and returns JSON: skill, importance (must / should / nice) and the chunk it came from.
2. **Retrieval**: for each requirement, pgvector finds the 3 closest resume chunks.
3. **Judge**: the LLM decides matched / partly / missing and must quote the resume chunk it used. Labels it returns are checked against real chunks, so it cannot cite something that does not exist.
4. **Score**: plain Python, not the LLM, in two parts:
   - **Requirement match**: `must = 3, should = 2, nice = 1` weights × `matched = 1, partly = 0.5, missing = 0`. The judge is strict: a skill that only appears in a skills list counts as "partly".
   - **ATS readiness** (`backend/app/ats.py`): exact keyword coverage, standard sections, results with numbers, action verbs and length, the checks applicant tracking systems and recruiters' first scan apply.
   - **Final score = 65% requirement match + 35% ATS readiness**, so a resume that matches every requirement but is thin or poorly structured does not get 100%.
5. **Coach**: the LLM rewrites resume lines and writes interview questions, told never to invent facts.

## Run it

You need **Docker Desktop**. A free **Groq API key** is optional (without it the app runs in demo mode).

```bash
cp .env.example .env          # then paste your key after LLM_API_KEY=
docker compose up --build
```

| Open | What |
|---|---|
| http://localhost:8080 | the app |
| http://localhost:8000/docs | interactive API docs |
| http://localhost:8001/mcp | MCP server |

Click **Try it with a sample resume** on the first screen to see a full report in a few seconds.

### Connect Claude Desktop (MCP)

With the app running, add this to Claude Desktop's config (Settings → Developer → Edit Config) and restart Claude:

```json
{
  "mcpServers": {
    "jobfit": { "command": "npx", "args": ["mcp-remote", "http://localhost:8001/mcp"] }
  }
}
```

Then ask Claude: *"Use JobFit to list my documents and analyse resume 1 against job 2."*
To inspect the tools without Claude: `npx @modelcontextprotocol/inspector` and connect to `http://localhost:8001/mcp`.

## Develop without Docker

```bash
# backend (needs a Postgres with pgvector)
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# frontend (proxies /api to :8000)
cd frontend && npm install && npm run dev
```

Tests and eval:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://jobfit:jobfit@localhost:5432/jobfit_test pytest
python -m evals.run_eval
```

## CI/CD

Every push and pull request runs:

1. **Lint**: ruff (Python), and the frontend production build
2. **Tests**: 29 pytest tests against a real Postgres + pgvector service container, with an offline embedder and a fake LLM so they are fast and free
3. **Eval**: the golden set in demo mode on every run; with the real model too when the `LLM_API_KEY` repository secret is set
4. **Docker**: on `main`, builds and publishes `jobfit-api` and `jobfit-web` images to GitHub Container Registry

## Design decisions

- **Score computed in code, not by the LLM**, so it is explainable and stable.
- **Citations are validated**: a chunk label the model returns is kept only if it really exists.
- **Any OpenAI-compatible LLM works**: change `LLM_BASE_URL` and `LLM_MODEL` to switch from Groq to another provider.
- **Embeddings run locally** in the API container, baked into the image at build time.
- **The MCP server is a thin client of the REST API**, so the same logic serves the web app, the agent and Claude.

---

Built by [Sundas Maria Hayat](https://github.com/sundas-stack).
