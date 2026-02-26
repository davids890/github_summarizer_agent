# GitHub Repository Summarizer

A full-stack app that takes a GitHub repository URL and returns a structured, AI-generated summary — covering purpose, tech stack, architecture, key components, and setup instructions.

Users can bring their own OpenAI API key or fall back to a server-side key.

![Python](https://img.shields.io/badge/Python-FastAPI-009688?style=flat&logo=fastapi)
![React](https://img.shields.io/badge/React-Vite-61DAFB?style=flat&logo=react)
![OpenAI](https://img.shields.io/badge/LLM-GPT--4o-412991?style=flat&logo=openai)

## Features

- Paste any public GitHub repo URL and get an instant AI summary
- Bring your own OpenAI API key (or use a server default)
- Smart file prioritization — READMEs, entry points, and config files analyzed first
- Token-aware context window protection (100K token cap via `tiktoken`)
- Skips binaries, lock files, images, and other noise automatically
- Clean, responsive React frontend with Markdown rendering

## Quick Start

### Backend

```bash
git clone <this-repo>
cd summarize_github_repo
pip install -r requirements.txt
```

Create a `.env` file:

```
OPENAI_API_KEY=sk-...
```

Start the server:

```bash
python main.py   # runs on http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # runs on http://localhost:5173
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

## API

### `POST /summarize`

| Field      | Type   | Required | Description                                     |
| ---------- | ------ | -------- | ----------------------------------------------- |
| `url`      | string | yes      | GitHub repository URL                           |
| `priority` | string | no       | `"all"` (default), `"high"`, or `"high+medium"` |
| `api_key`  | string | no       | Your OpenAI API key (falls back to server key)  |

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/fastapi/fastapi"}'
```

### `GET /health`

Returns `{"status": "ok"}`.

## How It Works

1. **Parse** — Extract owner/repo from the GitHub URL
2. **Clone** — Shallow clone (`git clone --depth 1`) into a temp directory
3. **Filter** — Walk the repo, skip binaries/noise, sort files into priority tiers
4. **Read** — Build a directory tree + read file contents within a 100K token budget
5. **Summarize** — Send context to GPT-4o with a structured prompt
6. **Cleanup** — Delete the temp clone

## Project Structure

```
├── main.py                  # FastAPI app + /summarize endpoint
├── repo_service.py          # Core pipeline (parse → clone → filter → read → summarize)
├── requirements.txt         # Python dependencies
├── .env                     # OpenAI API key (not committed)
├── playground.ipynb         # Development notebook
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Main UI component
│   │   └── index.css        # Global styles + summary formatting
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Tech Stack

| Layer     | Technology                           |
| --------- | ------------------------------------ |
| Backend   | Python, FastAPI, Uvicorn             |
| Frontend  | React 19, TypeScript, Vite, Tailwind |
| LLM       | OpenAI GPT-4o                        |
| Tokenizer | tiktoken                             |
| Markdown  | react-markdown                       |

## Future Ideas

- GitHub token support for private repos
- Local model support via Ollama
- Support for alternative LLM API keys (Anthropic, etc.)
