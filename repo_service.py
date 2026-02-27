import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import tiktoken
from openai import OpenAI

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "vendor", ".tox", ".mypy_cache",
    ".pytest_cache", "coverage", ".idea", ".vscode",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".mov",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".zip", ".tar", ".gz", ".bz2",
    ".lock", ".min.js", ".min.css",
    ".pyc", ".pyo", ".so", ".dll", ".dylib",
    ".DS_Store", ".gitignore",
}

MAX_FILE_SIZE = 100_000
MAX_CONTEXT_TOKENS = 100_000

_enc = tiktoken.encoding_for_model("gpt-4o")


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


# ── Prompts ──────────────────────────────────────────────────────────────

SELECTOR_PROMPT = """\
You are a repository analyst. You will receive the full directory tree of a \
codebase. Your job is to select the **up to 20 most important files** that \
would give someone the best understanding of the project.

Prioritize (in rough order):
- README / docs at the root
- Entry points (main.py, index.ts, app.py, etc.)
- Core business-logic / domain modules
- Configuration files that reveal the stack (package.json, pyproject.toml, \
Cargo.toml, Dockerfile, etc.)
- API route definitions
- Key data models / schemas

Avoid:
- Test files (unless the project IS a test framework)
- Generated / config-only files (tsconfig, eslint, .prettierrc, etc.)
- Lock files, CI configs, changelogs

Return **only** a JSON object with a single key "files" whose value is an \
array of relative file paths, ordered from MOST important to LEAST important. \
No explanation, no markdown fences — just the raw JSON object.

Example:
{"files": ["README.md", "src/main.py", "src/core/engine.py"]}
"""

SUMMARIZE_PROMPT = """\
You are a code analyst. Given a repository's directory structure and selected \
file contents, produce a clear, human-readable summary.

Your summary should include these sections:
1. **Purpose** — What does this project do? (1-2 sentences)
2. **Tech Stack** — Languages, frameworks, and key dependencies
3. **Architecture** — How is the codebase organized? Key modules/packages
4. **Key Components** — The most important files/classes/functions and what they do
5. **Getting Started** — How to install and run the project (if discernible)

Keep it concise but informative. Focus on what matters most to someone seeing \
this project for the first time.
Do NOT include a title or heading like "Repository Summary" at the top. \
Start directly with the content."""


# ── Step 1: Parse GitHub URL ─────────────────────────────────────────────

def parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    parsed = urlparse(url)

    if parsed.hostname not in ("github.com", "www.github.com"):
        raise ValueError(f"Not a GitHub URL: {url}")

    parts = parsed.path.strip("/").split("/")

    if len(parts) < 2:
        raise ValueError(f"URL must include owner and repo: {url}")

    owner = parts[0]
    repo = re.sub(r"\.git$", "", parts[1])

    if not owner or not repo:
        raise ValueError(f"Could not extract owner/repo from: {url}")

    return owner, repo


# ── Step 2: Clone the Repository ─────────────────────────────────────────

def clone_repo(owner: str, repo: str) -> Path:
    """Shallow-clone a GitHub repo into a temp directory."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="repo_"))
    clone_url = f"https://github.com/{owner}/{repo}.git"

    subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, str(tmp_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    return tmp_dir


# ── Step 3: Collect all eligible file paths ──────────────────────────────

def collect_files(repo_path: Path) -> list[Path]:
    """Walk the repo, skip noise dirs/extensions, return all eligible files."""
    result = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for filename in files:
            filepath = Path(root) / filename

            if any(filename.endswith(ext) for ext in SKIP_EXTENSIONS):
                continue
            try:
                if filepath.stat().st_size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue

            result.append(filepath)

    return sorted(result, key=lambda f: str(f.relative_to(repo_path)))


# ── Step 4: Build directory tree string ──────────────────────────────────

def build_directory_tree(repo_path: Path, files: list[Path]) -> str:
    """Build a text representation of the directory structure."""
    lines = ["# Directory Structure", "```"]
    seen_dirs: set[Path] = set()

    for f in files:
        rel = f.relative_to(repo_path)
        for i in range(1, len(rel.parts)):
            dir_path = Path(*rel.parts[:i])
            if dir_path not in seen_dirs:
                seen_dirs.add(dir_path)
                indent = "  " * (len(dir_path.parts) - 1)
                lines.append(f"{indent}{dir_path.name}/")
        indent = "  " * (len(rel.parts) - 1)
        lines.append(f"{indent}{rel.name}")

    lines.append("```")
    return "\n".join(lines)


# ── Step 5: LLM Selector Agent ──────────────────────────────────────────

def select_important_files(
    tree: str, all_files: list[Path], repo_path: Path,
    api_key: str | None = None,
) -> list[Path]:
    """Ask GPT-4o to pick up to 20 most important files from the tree."""
    client = OpenAI(api_key=api_key) if api_key else OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SELECTOR_PROMPT},
            {"role": "user", "content": tree},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    selected_paths: list[str] = json.loads(raw).get("files", [])

    rel_to_abs = {str(f.relative_to(repo_path)): f for f in all_files}

    ordered: list[Path] = []
    for rel in selected_paths:
        if rel in rel_to_abs and rel_to_abs[rel] not in ordered:
            ordered.append(rel_to_abs[rel])
        if len(ordered) >= 20:
            break

    return ordered


# ── Step 6: Build context within token budget ────────────────────────────

def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within max_tokens, cutting at a line boundary."""
    tokens = _enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = _enc.decode(tokens[:max_tokens])
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    return truncated + "\n\n... [truncated] ..."


def build_context(
    repo_path: Path, tree: str, important_files: list[Path],
) -> str:
    """Assemble tree + file contents, trimming least-important files first
    so total context stays under MAX_CONTEXT_TOKENS."""

    system_tokens = _count_tokens(SUMMARIZE_PROMPT)
    token_budget = MAX_CONTEXT_TOKENS - system_tokens
    tree_tokens = _count_tokens(tree)

    file_chunks: list[tuple[str, int]] = []
    for filepath in important_files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = filepath.relative_to(repo_path)
        chunk = f"## File: {rel}\n```\n{content}\n```"
        file_chunks.append((chunk, _count_tokens(chunk)))

    total = tree_tokens + sum(t for _, t in file_chunks)

    while total > token_budget and file_chunks:
        removed_chunk, removed_tokens = file_chunks.pop()
        total -= removed_tokens

    parts = [tree] + [chunk for chunk, _ in file_chunks]
    context = "\n\n".join(parts)

    if _count_tokens(context) + system_tokens > MAX_CONTEXT_TOKENS:
        context = _truncate_to_tokens(context, token_budget)

    return context


# ── Step 7: Summarize with LLM ──────────────────────────────────────────

def summarize_repo(context: str, api_key: str | None = None) -> str:
    """Send repo context to the LLM and return a summary."""
    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SUMMARIZE_PROMPT},
            {"role": "user", "content": f"Summarize this repository:\n\n{context}"},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


# ── Full Pipeline ────────────────────────────────────────────────────────

def process_repo(url: str, api_key: str | None = None) -> str:
    """End-to-end: URL → clone → tree → select → read → summarize → cleanup."""
    owner, repo = parse_github_url(url)
    repo_path = clone_repo(owner, repo)

    try:
        all_files = collect_files(repo_path)
        tree = build_directory_tree(repo_path, all_files)
        important = select_important_files(tree, all_files, repo_path, api_key)
        context = build_context(repo_path, tree, important)
        summary = summarize_repo(context, api_key)
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)

    return summary
