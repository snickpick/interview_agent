import os
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
from pydantic import BaseModel

from database import (
    create_session,
    get_session,
    init_db,
    save_answer,
    update_session,
)
from questions import INTERVIEW_BLOCKS

load_dotenv()

app = FastAPI(title="Interview Agent")
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
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

SYSTEM_PROMPT = """You are a friendly but thorough interview assistant.
Evaluate the candidate's answer to the question. Provide brief constructive feedback.
Then indicate whether the answer is sufficient (is_done=True) or needs more detail (is_done=False).
Keep your feedback concise - 2-3 sentences maximum.
Be encouraging but honest."""


class EvalResult(BaseModel):
    feedback: str
    is_done: bool


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/start")
def start_interview(data: dict):
    name = data.get("name", "").strip()
    if not name:
        return {"error": "Name is required"}
    session_id = create_session(name)
    block = INTERVIEW_BLOCKS[0]
    return {
        "session_id": session_id,
        "block_name": block["name"],
        "question": block["questions"][0],
        "question_idx": 0,
        "block_idx": 0,
        "total_blocks": len(INTERVIEW_BLOCKS),
    }


@app.post("/api/answer")
def submit_answer(data: dict):
    session_id = data.get("session_id")
    answer = data.get("answer", "").strip()

    session = get_session(session_id)
    if not session:
        return {"error": "Invalid session"}

    block = INTERVIEW_BLOCKS[session["block_idx"]]
    question = block["questions"][session["question_idx"]]

    history = session["history"]
    history += f"\n[ANSWER] {answer}"

    try:
        parsed = get_client().beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Question: {question}\n\nAnswer: {answer}"},
            ],
            response_format=EvalResult,
        )
        result: EvalResult = parsed.choices[0].message.parsed
    except Exception as e:
        return {"error": f"AI evaluation failed: {str(e)}"}

    history += f"\n[FEEDBACK] {result.feedback}"
    save_answer(session_id, block["name"], question, answer, result.feedback)

    if result.is_done:
        next_question_idx = session["question_idx"] + 1
        next_block_idx = session["block_idx"]

        if next_question_idx >= len(block["questions"]):
            next_block_idx += 1
            next_question_idx = 0

        if next_block_idx >= len(INTERVIEW_BLOCKS):
            update_session(
                session_id,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            return {
                "feedback": result.feedback,
                "done": True,
                "message": "Interview completed! Thank you for your answers.",
            }
        else:
            next_block = INTERVIEW_BLOCKS[next_block_idx]
            update_session(
                session_id,
                block_idx=next_block_idx,
                question_idx=next_question_idx,
                history="",
            )
            return {
                "feedback": result.feedback,
                "done": False,
                "next_question": next_block["questions"][next_question_idx],
                "next_block_name": next_block["name"],
                "block_idx": next_block_idx,
                "question_idx": next_question_idx,
            }
    else:
        update_session(session_id, history=history)
        return {
            "feedback": result.feedback,
            "done": False,
            "repeat": True,
            "question": question,
        }


@app.get("/api/tts")
def text_to_speech(text: str):
    tts = gTTS(text=text, lang="en")
    buf = BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    return Response(content=buf.read(), media_type="audio/mpeg")
