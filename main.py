from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from dotenv import load_dotenv

from repo_service import process_repo, parse_github_url

load_dotenv()

app = FastAPI(
    title="GitHub Repository Summarizer",
    description="Takes a GitHub repo URL and returns a human-readable AI summary.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SummarizeRequest(BaseModel):
    url: HttpUrl
    priority: str = "all"  # "all", "high", "high+medium"
    api_key: str | None = None  # user's OpenAI API key (optional, falls back to .env)


class SummarizeResponse(BaseModel):
    url: str
    summary: str


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(request: SummarizeRequest):
    url = str(request.url)

    try:
        parse_github_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if request.priority not in ("all", "high", "high+medium"):
        raise HTTPException(status_code=400, detail="priority must be 'all', 'high', or 'high+medium'")

    try:
        summary = process_repo(url, priority=request.priority, api_key=request.api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process repo: {e}")

    return SummarizeResponse(url=url, summary=summary)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
