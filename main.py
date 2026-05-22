import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from gtts import gTTS
from openai import OpenAI

import uvicorn

from database import (
    create_session,
    get_session,
    get_answers,
    init_db,
    save_answer,
    update_session,
)
from questions import generate_questions, evaluate_answer, generate_summary

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Interview Bot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )
    return _client


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/start")
def start_interview(data: dict):
    name = data.get("name", "").strip()
    topic = data.get("topic", "").strip()
    if not name:
        return {"error": "Name is required"}
    if not topic:
        return {"error": "Topic is required"}

    client = get_client()
    questions = generate_questions(client, topic)

    session_id = create_session(name, topic, questions)

    return {
        "session_id": session_id,
        "name": name,
        "topic": topic,
        "question": questions[0],
        "question_idx": 0,
        "total_questions": len(questions),
    }


@app.post("/api/answer")
def submit_answer(data: dict):
    session_id = data.get("session_id")
    answer = data.get("answer", "").strip()

    session = get_session(session_id)
    if not session:
        return {"error": "Invalid session"}

    q_idx = session["question_idx"]
    question = session["questions"][q_idx]

    client = get_client()
    eval_result = evaluate_answer(client, question, answer)

    save_answer(
        session_id, question, answer, eval_result.score, eval_result.feedback
    )

    next_idx = q_idx + 1

    if next_idx >= len(session["questions"]):
        all_answers = get_answers(session_id)
        qa_pairs = [
            (a["question"], a["answer"], a["score"], a["feedback"])
            for a in all_answers
        ]
        summary_result = generate_summary(client, session["topic"], qa_pairs)

        total_score = sum(a["score"] for a in all_answers)

        if total_score >= 90:
            fit = "Best Fit"
        elif total_score >= 75:
            fit = "Fit"
        else:
            fit = "Not Fit"

        update_session(
            session_id,
            question_idx=next_idx,
            total_score=total_score,
            summary=summary_result.summary,
            strengths=summary_result.strengths,
            weaknesses=summary_result.weaknesses,
            fit_result=fit,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        return {
            "feedback": eval_result.feedback,
            "score": eval_result.score,
            "done": True,
            "total_score": total_score,
            "total_questions": len(session["questions"]),
            "fit": fit,
            "strengths": summary_result.strengths,
            "weaknesses": summary_result.weaknesses,
            "summary": summary_result.summary,
        }

    update_session(session_id, question_idx=next_idx)

    return {
        "feedback": eval_result.feedback,
        "score": eval_result.score,
        "done": False,
        "next_question": session["questions"][next_idx],
        "question_idx": next_idx,
        "total_questions": len(session["questions"]),
    }


@app.get("/api/tts")
def text_to_speech(text: str):
    tts = gTTS(text=text, lang="en")
    buf = BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return Response(content=buf.read(), media_type="audio/mpeg")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
