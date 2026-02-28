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
    ".pytest_cache", "coverage", ".idea", ".vscode", "docs", ".github",
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

HIGH_PRIORITY_NAMES = {
    "README.md", "readme.md", "README.rst",
    "main.py", "app.py", "index.py", "server.py", "cli.py",
    "index.ts", "index.js", "app.ts", "app.js", "main.ts", "main.js",
    "setup.py", "setup.cfg", "pyproject.toml",
    "package.json", "Cargo.toml", "go.mod",
    "Makefile", "Dockerfile", "docker-compose.yml",
    "requirements.txt",
}

LOW_PRIORITY_DIRS = {
    "test", "tests", "spec", "specs", "examples", "example",
    "docs_src", "benchmarks", "scripts",
}

MAX_FILE_SIZE = 100_000
MAX_TOTAL_CHARS = 500_000
MAX_FILES = 150
MAX_CONTEXT_TOKENS = 100_000

SYSTEM_PROMPT = """You are a code analyst. Given a repository's directory structure and file contents, produce a clear, human-readable summary.

Your summary should include these sections:
1. **Purpose** — What does this project do? (1-2 sentences)
2. **Repository supports** - Proposed solution**: what this repo suggest the developers / users ? for example: you can use this repo to train detection model etc..
3. **Key Components** — The most important files/classes/functions and what they do
4. **Architecture** — How is the codebase organized? Key modules/packages
5. **Tech Stack** — Languages, frameworks, and key dependencies
6. **Getting Started** — How to install and run the project (if discernible from the code)

Keep the summary concise but informative. Focus on what matters most to someone seeing this project for the first time.
Do NOT include a title or heading like "Repository Summary" at the top. Start directly with the content."""


# --- Step 1: Parse GitHub URL ---

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


# --- Step 2: Clone the Repository ---

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


# --- Step 3: Filter Relevant Files ---

def _prioritize_files(
    files: list[Path], repo_path: Path
) -> tuple[list[Path], list[Path], list[Path]]:
    """Sort files into priority tiers. Returns (high, medium, low)."""
    high, medium, low = [], [], []

    for f in files:
        rel = f.relative_to(repo_path)
        parts = set(rel.parts)

        if rel.name in HIGH_PRIORITY_NAMES:
            high.append(f)
        elif parts & LOW_PRIORITY_DIRS:
            low.append(f)
        else:
            medium.append(f)

    key = lambda f: (len(f.relative_to(repo_path).parts), str(f))
    high.sort(key=key)
    medium.sort(key=key)
    low.sort(key=key)

    return high, medium, low


def filter_files(repo_path: Path, priority: str = "all") -> list[Path]:
    """Walk the cloned repo, filter, and return priority-sorted file paths.

    priority: "all" (default), "high", "high+medium"
    """
    filtered = []

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

            filtered.append(filepath)

    high, medium, low = _prioritize_files(filtered, repo_path)

    if priority == "high":
        return high
    elif priority == "high+medium":
        return high + medium
    return high + medium + low


# --- Step 4: Read File Contents ---

def _build_directory_tree(repo_path: Path, files: list[Path]) -> str:
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


_enc = tiktoken.encoding_for_model("gpt-4o")

FULL_READ_NAMES = {
    "README.md", "readme.md", "README.rst",
    "main.py", "app.py", "index.py",
}


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


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


def read_all_contents(repo_path: Path, files: list[Path]) -> str:
    """Build directory tree + read filtered files into a context string.

    High-priority files (README, main entry points) are included in full.
    Remaining files share the leftover token budget equally, each truncated
    to its fair share so every file gets represented.
    """
    tree = _build_directory_tree(repo_path, files)

    system_tokens = _count_tokens(SYSTEM_PROMPT)
    token_budget = MAX_CONTEXT_TOKENS - system_tokens
    total_tokens = _count_tokens(tree)

    files_to_read = files[:MAX_FILES]

    full_read_files: list[tuple[Path, str]] = []
    trimmable_files: list[tuple[Path, str]] = []

    for filepath in files_to_read:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if filepath.name in FULL_READ_NAMES:
            full_read_files.append((filepath, content))
        else:
            trimmable_files.append((filepath, content))

    context_parts = []

    for filepath, content in full_read_files:
        rel_path = filepath.relative_to(repo_path)
        chunk = f"## File: {rel_path}\n```\n{content}\n```"
        chunk_tokens = _count_tokens(chunk)
        total_tokens += chunk_tokens
        context_parts.append(chunk)

    remaining_budget = token_budget - total_tokens
    if trimmable_files and remaining_budget > 0:
        per_file_budget = remaining_budget // len(trimmable_files)
        per_file_budget = max(per_file_budget, 50)

        for filepath, content in trimmable_files:
            rel_path = filepath.relative_to(repo_path)
            chunk = f"## File: {rel_path}\n```\n{content}\n```"
            chunk_tokens = _count_tokens(chunk)

            if chunk_tokens > per_file_budget:
                content = _truncate_to_tokens(content, per_file_budget - 20)
                chunk = f"## File: {rel_path}\n```\n{content}\n```"
                chunk_tokens = _count_tokens(chunk)

            if total_tokens + chunk_tokens > token_budget:
                break

            context_parts.append(chunk)
            total_tokens += chunk_tokens

    return tree + "\n\n" + "\n\n".join(context_parts)


# --- Step 5: Summarize with LLM ---

def summarize_repo(context: str, api_key: str | None = None) -> str:
    """Send repo context to the LLM and return a summary."""
    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Summarize this repository:\n\n{context}"},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


# --- Step 6: LLM-based File Selection Agent ---

SELECT_FILES_PROMPT = """You are a code-repository analyst. You will receive a list of file paths from a GitHub repository.

Your task: select up to 20 files that are **most important** for understanding the project. Prioritize:
1. README and documentation entry points
2. Main entry points (main.py, app.py, index.ts, etc.)
3. Core business logic / domain modules
4. Configuration & dependency manifests (package.json, pyproject.toml, etc.)
5. API route definitions or CLI handlers
6. Key model/schema definitions

Avoid selecting:
- Test files (unless they are the only way to understand the API)
- Generated or boilerplate files
- Assets, configs for linters/CI, or lockfiles

Return ONLY a JSON array of the selected file paths (as strings), nothing else.
Example: ["README.md", "src/main.py", "src/models.py"]"""


def select_important_files(
    repo_path: Path,
    files: list[Path],
    api_key: str | None = None,
    max_files: int = 20,
) -> list[Path]:
    """Use an LLM to pick the most important files (up to *max_files*) from the repo."""
    if len(files) <= max_files:
        return files

    rel_paths = [str(f.relative_to(repo_path)) for f in files]
    file_list_text = "\n".join(rel_paths)

    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SELECT_FILES_PROMPT},
            {"role": "user", "content": file_list_text},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        selected: list[str] = json.loads(raw)
    except json.JSONDecodeError:
        return files[:max_files]

    rel_to_abs = {str(f.relative_to(repo_path)): f for f in files}
    result = [rel_to_abs[p] for p in selected if p in rel_to_abs]

    return result or files[:max_files]


# --- Full Pipeline ---

def process_repo(url: str, priority: str = "all", api_key: str | None = None) -> str:
    """End-to-end: URL → clone → filter → read → summarize → cleanup."""
    owner, repo = parse_github_url(url)
    repo_path = clone_repo(owner, repo)

    try:
        files = filter_files(repo_path, priority=priority)
        important_files = select_important_files(repo_path, files, api_key=api_key)
        context = read_all_contents(repo_path, important_files)
        summary = summarize_repo(context, api_key=api_key)
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)

    return summary
