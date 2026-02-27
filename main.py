from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from dotenv import load_dotenv

from repo_service import process_repo, parse_github_url  # noqa: F401

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
    api_key: str | None = None


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

    try:
        summary = process_repo(url, api_key=request.api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process repo: {e}")

    return SummarizeResponse(url=url, summary=summary)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
