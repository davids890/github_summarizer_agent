# GitHub Repository Summarizer

A full-stack app that takes a GitHub repository URL and returns a structured, AI-generated summary — covering purpose, tech stack, architecture, key components, and setup instructions.

Users can bring their own OpenAI API key or fall back to a server-side key.

![Python](https://img.shields.io/badge/Python-FastAPI-009688?style=flat&logo=fastapi)
![React](https://img.shields.io/badge/React-Vite-61DAFB?style=flat&logo=react)
![OpenAI](https://img.shields.io/badge/LLM-GPT--4o-412991?style=flat&logo=openai)

## Features

- Paste any public GitHub repo URL and get an instant AI summary
- Bring your own OpenAI API key (or use a server default)
- Two-agent architecture: a **Selector Agent** picks the most important files, then a **Summarizer Agent** produces the final summary
- Token-aware context window (100K token cap via `tiktoken`) — drops least-important files first if the budget is exceeded
- Skips binaries, lock files, images, and other noise automatically
- Clean, responsive React frontend with Markdown rendering

## Setup & Run (from scratch)

### Prerequisites

- Python 3.11+
- Node.js 18+ and [pnpm](https://pnpm.io/installation)
- Git
- An OpenAI API key

### 1. Clone the repository

```bash
git clone <this-repo>
cd github_summarizer_agent
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Create a `.env` file

```
OPENAI_API_KEY=sk-...
```

### 4. Install frontend dependencies

```bash
cd frontend
pnpm install
cd ..
```

### 5. Run both servers

```bash
./run.sh
```

This starts the FastAPI backend on `http://localhost:8000` and the React frontend on `http://localhost:5173`.

Alternatively, run them separately:

```bash
# Terminal 1 — backend
python main.py

# Terminal 2 — frontend
cd frontend && pnpm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

## Model Choice

The app uses **OpenAI GPT-4o** for both agents. GPT-4o offers the best balance of reasoning quality, large context window (128K tokens), and structured output support (`response_format: json_object`), which the selector agent relies on to return a clean ranked file list.

## How Repository Contents Are Handled

### What gets included

1. **Shallow clone** — the repo is cloned with `--depth 1` (only the latest commit, no history) into a temp directory.
2. **File collection** — all files are walked, filtering out noise (see below). The full directory tree is built from the surviving files.
3. **Selector Agent** — the directory tree is sent to GPT-4o, which picks **up to 20 most important files** ranked by importance. It prioritizes READMEs, entry points, core business logic, config files that reveal the stack (package.json, Dockerfile, etc.), API routes, and data models.
4. **Context assembly** — the directory tree + selected file contents are assembled. If the total exceeds the 100K token budget, files are dropped from the bottom of the ranked list (least important first) until it fits.
5. **Summarizer Agent** — the trimmed context is sent to GPT-4o with a structured prompt requesting Purpose, Tech Stack, Architecture, Key Components, and Getting Started sections.
6. **Cleanup** — the cloned directory is deleted in a `finally` block, regardless of success or failure.

### What gets skipped

| Category | Examples |
| --- | --- |
| **Directories** | `node_modules`, `.git`, `__pycache__`, `venv`, `dist`, `build`, `.next`, `vendor`, `.idea`, `.vscode` |
| **Binary / media** | `.png`, `.jpg`, `.gif`, `.svg`, `.mp4`, `.pdf`, `.zip`, `.woff` |
| **Generated / lock** | `.lock`, `.min.js`, `.min.css`, `.pyc`, `.so`, `.dll` |
| **Oversized files** | Any file > 100 KB |

This aggressive filtering ensures the LLM only sees meaningful source code and configuration, not noise that would waste the token budget.

## API

### `POST /summarize`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `url` | string | yes | GitHub repository URL |
| `api_key` | string | no | Your OpenAI API key (falls back to server key) |

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/fastapi/fastapi"}'
```

### `GET /health`

Returns `{"status": "ok"}`.

## Project Structure

```
├── main.py                  # FastAPI app + /summarize endpoint
├── repo_service.py          # Core pipeline (clone → tree → select → read → summarize)
├── run.sh                   # Starts backend + frontend together
├── requirements.txt         # Python dependencies
├── .env                     # OpenAI API key (not committed)
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Main UI component
│   │   └── index.css        # Global styles + summary formatting
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python, FastAPI, Uvicorn |
| Frontend | React 19, TypeScript, Vite, Tailwind |
| LLM | OpenAI GPT-4o (selector + summarizer agents) |
| Tokenizer | tiktoken |
| Markdown | react-markdown |

## Future Ideas

- GitHub token support for private repos
- Local model support via Ollama
- Support for alternative LLM API keys (Anthropic, etc.)
