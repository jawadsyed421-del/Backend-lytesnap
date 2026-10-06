"""LyteSnap AI backend — FastAPI ASGI entrypoint.

Vercel imports the module-level `app` object from this file
(see [tool.vercel] entrypoint in pyproject.toml).

Local:  uvicorn app:app --reload
"""
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="LyteSnap AI Backend API",
    description="HTTP API for LyteSnap AI feed reshaping backend",
    version="1.0.0",
)

# Enable CORS for web apps and frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
SCHEDULE_PATH = BASE_DIR / "schedules" / "schedule_state.json"

# Serverless filesystems are read-only apart from /tmp, so config writes land
# there. This survives a warm instance only — see README for durable storage.
IS_SERVERLESS = bool(os.environ.get("VERCEL"))
CONFIG_WRITE_PATH = Path("/tmp/config.json") if IS_SERVERLESS else CONFIG_PATH


class ClassifyRequest(BaseModel):
    topic: str
    titles: List[str]
    api_key: Optional[str] = None


def _read_config() -> Dict[str, Any]:
    """Read the /tmp override if an update landed there, else the bundled file."""
    for path in (CONFIG_WRITE_PATH, CONFIG_PATH):
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "LyteSnap AI Backend",
        "version": "1.0.0",
        "platform": "Vercel Serverless Function" if IS_SERVERLESS else "local",
        "endpoints": [
            "/api/health",
            "/api/config",
            "/api/schedule",
            "/api/classify",
            "/docs",
        ],
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "has_anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@app.get("/api/config")
def get_config():
    try:
        return _read_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {str(e)}")


@app.post("/api/config")
def update_config(config: Dict[str, Any]):
    try:
        current = _read_config()
        current.update(config)
        CONFIG_WRITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_WRITE_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        return {"status": "success", "persistent": not IS_SERVERLESS, "config": current}
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")


@app.get("/api/schedule")
def get_schedule():
    if not SCHEDULE_PATH.exists():
        return {"active": False}
    try:
        with open(SCHEDULE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"active": False, "error": str(e)}


@app.post("/api/classify")
def classify_titles(payload: ClassifyRequest):
    api_key = payload.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="ANTHROPIC_API_KEY not configured in environment or request body.",
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = (
            f"You are a video topic classifier. The user wants to reshape their feed to focus on: '{payload.topic}'.\n"
            f"Given the following video titles, classify each title as 1 if it is relevant to '{payload.topic}', "
            f"or 0 if it is irrelevant or clickbait.\n\n"
            f"Titles:\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(payload.titles)]) + "\n\n"
            f"Return only a JSON array of numbers corresponding to each title, e.g. [1, 0, 1]."
        )

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        content_text = response.content[0].text

        try:
            scores = json.loads(content_text.strip())
        except json.JSONDecodeError:
            scores = None

        return {
            "topic": payload.topic,
            "scores": scores,
            "raw_response": content_text,
            "count": len(payload.titles),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anthropic API classification error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
