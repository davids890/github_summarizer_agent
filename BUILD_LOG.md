# Building a GitHub Repo Summarizer — From Idea to Working App in a Few Hours

## The Idea

I wanted a simple tool: paste a GitHub repo URL, get a clean AI-generated summary. Useful for quickly understanding unfamiliar open-source projects without digging through the code yourself.

## What I Built

A full-stack app with a Python/FastAPI backend and a React frontend.

**The backend** takes a GitHub URL, shallow-clones the repo, intelligently filters and prioritizes files (READMEs and entry points first, skipping binaries and noise), reads them into a structured context, and sends it to GPT-4o for summarization.

**The frontend** is a clean single-page app where you paste a URL, optionally provide your own OpenAI API key, and get a nicely formatted Markdown summary.

## How I Approached It

### Step 1 — Core Pipeline (Backend)

I started in a Jupyter notebook prototyping the pipeline:
- Parse the GitHub URL to extract owner/repo
- Shallow clone with `git clone --depth 1` (fast, no history)
- Walk the directory and filter out noise (node_modules, images, lock files, etc.)
- Prioritize files into tiers — high priority (README, main entry points, config), medium, and low (tests, examples)
- Read file contents with a character budget so we don't overwhelm the model
- Send everything to OpenAI with a structured system prompt

Once it worked in the notebook, I moved it into `repo_service.py` as a clean pipeline.

### Step 2 — API Layer

Wrapped the pipeline in a FastAPI app (`main.py`) with:
- A `POST /summarize` endpoint that accepts a URL, priority filter, and optional API key
- CORS middleware so the frontend can call it
- Input validation and error handling

### Step 3 — Frontend

Built a React app with Vite and Tailwind CSS:
- Minimalist design with a large "Summarize." headline
- Input fields for the repo URL and optional API key
- Loading spinner while the backend processes
- Markdown rendering for the summary output using react-markdown
- Custom CSS for clean typography on the summary (styled lists, code blocks, headings)

### Step 4 — Context Window Protection

Hit a wall when testing on larger repos — the OpenAI API rejected requests because the context exceeded 128K tokens. The original character-based budget wasn't accurate enough.

**Fix:** Added `tiktoken` for proper token counting. The pipeline now counts tokens as it adds files and stops at 100K tokens, leaving room for the system prompt and the model's response. No more 400 errors.

### Step 5 — UI Polish

Spent time fine-tuning the summary layout:
- Aligned top-level section titles (Purpose, Tech Stack, etc.) flush with the "Summary" heading
- Kept nested bullet points indented for readability
- Adjusted spacing and margins throughout

## Tech Decisions

- **Shallow clone** instead of the GitHub API — simpler, gets all files, no rate limits for public repos
- **File prioritization** — ensures the most important files are always included even if the repo exceeds the token budget
- **tiktoken** — accurate token counting beats character estimation; prevents API errors on large repos
- **Bring your own key** — users can provide their own OpenAI key, making it easy to share without exposing mine

## What's Next

- Add GitHub token support for private repositories
- Option to use local models via Ollama (no API key needed)
- Support for other LLM providers
