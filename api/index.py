import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="LyteSnap AI Backend API",
    description="HTTP API for LyteSnap AI feed reshaping backend",
    version="1.0.0"
)

# Enable CORS for web apps and frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
SCHEDULE_PATH = BASE_DIR / "schedules" / "schedule_state.json"

class ConfigModel(BaseModel):
    session_duration_minutes: Optional[int] = 45
    max_homepage_watches_per_cycle: Optional[int] = 3
    watch_pct_min: Optional[float] = 0.6
    watch_pct_max: Optional[float] = 0.9
    watch_cap_seconds: Optional[int] = 300
    extra: Optional[Dict[str, Any]] = None

class ClassifyRequest(BaseModel):
    topic: str
    titles: List[str]
    api_key: Optional[str] = None

class ScoreRequest(BaseModel):
    topic: str
    sample_size: Optional[int] = 20

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "LyteSnap AI Backend",
        "version": "1.0.0",
        "platform": "Vercel Serverless Function",
        "endpoints": [
            "/api/health",
            "/api/config",
            "/api/schedule",
            "/api/classify",
            "/docs"
        ]
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "has_anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY"))
    }

@app.get("/api/config")
def get_config():
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {str(e)}")

@app.post("/api/config")
def update_config(config: Dict[str, Any]):
    try:
        current = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                current = json.load(f)
        current.update(config)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        return {"status": "success", "config": current}
    except Exception as e:
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
            detail="ANTHROPIC_API_KEY not configured in environment or request body."
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = (
            f"You are a video topic classifier. The user wants to reshape their feed to focus on: '{payload.topic}'.\n"
            f"Given the following video titles, classify each title as 1 if it is relevant to '{payload.topic}', "
            f"or 0 if it is irrelevant or clickbait.\n\n"
            f"Titles:\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(payload.titles)]) + "\n\n"
            f"Return JSON array of numbers corresponding to each title, e.g. [1, 0, 1]."
        )

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        content_text = response.content[0].text
        return {
            "topic": payload.topic,
            "raw_response": content_text,
            "count": len(payload.titles)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anthropic API classification error: {str(e)}")
