# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from db import Base, engine, get_session
import models, schemas
from scraper import scrape_wikipedia, ScrapeError
from llm import generate_quiz_payload, LLMError
from utils import normalize_payload

# -----------------------------------------------------------------------------
# App & CORS
# -----------------------------------------------------------------------------
app = FastAPI(title="DeepKlarity – AI Wiki Quiz Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables at startup
Base.metadata.create_all(bind=engine)

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok"}

# -----------------------------------------------------------------------------
# LLM smoke test (quick check that Gemini works)
# -----------------------------------------------------------------------------
# --- LLM smoke test ---
@app.get("/api/llm-test")
def llm_test():
    from llm import ping_llm
    return ping_llm()


# -----------------------------------------------------------------------------
# Scraper smoke test (quick check that Wikipedia fetch works)
# -----------------------------------------------------------------------------
class UrlIn(BaseModel):
    url: HttpUrl

@app.post("/api/scrape")
def scrape_only(payload: UrlIn):
    try:
        title, summary, text_blob, _ = scrape_wikipedia(str(payload.url))
        return {
            "ok": True,
            "title": title,
            "summary_len": len(summary),
            "text_len": len(text_blob),
        }
    except ScrapeError as e:
        return {"ok": False, "error": str(e)}

# -----------------------------------------------------------------------------
# Generate quiz (scrape + LLM + store + return)
# -----------------------------------------------------------------------------
@app.post("/api/generate", response_model=schemas.QuizOut)
def generate_quiz(payload: schemas.GenerateIn):
    url = str(payload.url)

    with get_session() as db:  # type: Session
        # 1) Scrape Wikipedia
        try:
            title, summary, text_blob, raw_html = scrape_wikipedia(url)
        except ScrapeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 2) Call LLM to generate study pack + quiz
        try:
            raw = generate_quiz_payload(url=url, article_text=text_blob)
            data = normalize_payload(raw)
        except LLMError as e:
            raise HTTPException(status_code=502, detail=str(e))

        # 3) Upsert by URL (simple cache: replace old row if exists)
        existing = db.query(models.Quiz).filter(models.Quiz.url == url).first()
        if existing:
            db.delete(existing)
            db.commit()

        quiz_row = models.Quiz(
            url=url,
            title=data["title"] or title,
            summary=data["summary"] or summary,
            key_entities=data["key_entities"],
            sections=data["sections"],
            related_topics=data["related_topics"],
            raw_html=raw_html,
        )
        db.add(quiz_row)
        db.flush()

        for q in data["quiz"]:
            db.add(models.Question(
                quiz_id=quiz_row.id,
                prompt=q["prompt"],
                options=q["options"],
                answer=q["answer"],
                difficulty=q.get("difficulty"),
                explanation=q.get("explanation"),
            ))

        db.commit()
        db.refresh(quiz_row)

        # 4) Shape response JSON
        out = {
            "id": quiz_row.id,
            "url": quiz_row.url,
            "title": quiz_row.title,
            "summary": quiz_row.summary,
            "key_entities": quiz_row.key_entities or {"people": [], "organizations": [], "locations": []},
            "sections": quiz_row.sections or [],
            "quiz": [
                {
                    "prompt": q.prompt,
                    "options": q.options,
                    "answer": q.answer,
                    "difficulty": q.difficulty,
                    "explanation": q.explanation,
                } for q in quiz_row.questions
            ],
            "related_topics": quiz_row.related_topics or [],
        }

        # The Pydantic model expects "question" instead of "prompt"
        out["quiz"] = [{"question": x.pop("prompt"), **x} for x in out["quiz"]]
        return out

# -----------------------------------------------------------------------------
# History list
# -----------------------------------------------------------------------------
@app.get("/api/quizzes", response_model=schemas.HistoryOut)
def list_quizzes():
    with get_session() as db:
        rows = db.query(models.Quiz).order_by(models.Quiz.created_at.desc()).all()
        return {
            "items": [
                {
                    "id": r.id,
                    "url": r.url,
                    "title": r.title,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        }

# -----------------------------------------------------------------------------
# Get quiz by id
# -----------------------------------------------------------------------------
@app.get("/api/quizzes/{quiz_id}", response_model=schemas.QuizOut)
def get_quiz(quiz_id: int):
    with get_session() as db:
        r = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="Quiz not found")

        out = {
            "id": r.id,
            "url": r.url,
            "title": r.title,
            "summary": r.summary,
            "key_entities": r.key_entities or {"people": [], "organizations": [], "locations": []},
            "sections": r.sections or [],
            "quiz": [
                {
                    "prompt": q.prompt,
                    "options": q.options,
                    "answer": q.answer,
                    "difficulty": q.difficulty,
                    "explanation": q.explanation,
                } for q in r.questions
            ],
            "related_topics": r.related_topics or [],
        }
        out["quiz"] = [{"question": x.pop("prompt"), **x} for x in out["quiz"]]
        return out
