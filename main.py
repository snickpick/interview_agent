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

from agent import InterviewAgent
from database import (
    create_session,
    get_answers,
    get_memory_state,
    get_session,
    init_db,
    save_answer,
    save_memory_state,
    update_session,
)
from memory import InterviewMemory

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


def load_agent(session_id):
    client = get_client()
    state = get_memory_state(session_id)
    if state:
        return InterviewAgent.from_dict(client, state)
    return InterviewAgent(client=client)


def save_agent(session_id, agent):
    save_memory_state(session_id, agent.to_dict())


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/start")
def start_interview(data: dict):
    name = data.get("name", "").strip()
    topic = data.get("topic", "").strip()
    num_questions = data.get("num_questions", 10)

    if not name:
        return {"error": "Name is required"}
    if not topic:
        return {"error": "Topic is required"}
    if not isinstance(num_questions, int) or num_questions < 1:
        return {"error": "num_questions must be a positive integer"}

    client = get_client()
    agent = InterviewAgent(
        client=client,
        memory=InterviewMemory(total_questions=num_questions),
    )
    questions = agent.generate_questions(topic)
    session_id = create_session(name, topic, questions, num_questions=num_questions)
    save_agent(session_id, agent)

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

    agent = load_agent(session_id)
    eval_result = agent.evaluate_answer(question, answer, q_idx)

    save_answer(
        session_id, question, answer, eval_result.score, eval_result.feedback
    )

    next_idx = q_idx + 1

    if next_idx >= len(session["questions"]):
        summary_result = agent.generate_summary(session["topic"])

        all_answers = get_answers(session_id)
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
        save_agent(session_id, agent)

        return {
            "feedback": eval_result.feedback,
            "acknowledgment": eval_result.acknowledgment,
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
    save_agent(session_id, agent)

    return {
        "feedback": eval_result.feedback,
        "acknowledgment": eval_result.acknowledgment,
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
