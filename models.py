from pydantic import BaseModel


class QuestionList(BaseModel):
    questions: list[str]


class AnswerEval(BaseModel):
    score: int
    feedback: str


class FinalEval(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
    summary: str
