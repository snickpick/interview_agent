from typing import Optional

from openai import OpenAI

from memory import InterviewMemory
from models import AnswerEval, FinalEval, QuestionList


class InterviewAgent:
    def __init__(
        self,
        client: OpenAI,
        memory: Optional[InterviewMemory] = None,
    ):
        self.client = client
        self.memory = memory or InterviewMemory()

    @classmethod
    def from_dict(cls, client: OpenAI, data: dict):
        memory = InterviewMemory.from_dict(data)
        return cls(client=client, memory=memory)

    def generate_questions(self, topic: str) -> list[str]:
        result = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical interviewer. "
                        "Generate interview questions about the given topic. "
                        "Cover basic, intermediate, and advanced concepts. "
                        "Questions should test understanding, not just memorization. "
                        "Return them as a JSON object with a 'questions' key containing an array of strings."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate {self.memory.total_questions} interview questions about: {topic}"
                    ),
                },
            ],
            response_format=QuestionList,
        )
        questions = result.choices[0].message.parsed.questions
        self.memory.add_turn("system", f"Topic: {topic}")
        return questions

    def evaluate_answer(
        self, question: str, answer: str, question_idx: int
    ) -> AnswerEval:
        context = self.memory.get_context()

        system_content = (
            "You are an expert interviewer evaluating a candidate's answer. "
            "Score from 0-10 based on accuracy, completeness, clarity, and depth. "
            "Be strict - a perfect score of 10 means the answer is comprehensive and flawless. "
            "Provide brief constructive feedback (1-2 sentences). "
        )
        if context:
            system_content += (
                "\n\nConsider the candidate's performance trajectory from the "
                "interview history below. Be consistent with previous scores.\n\n"
                f"Interview history:\n{context}"
            )

        result = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nAnswer: {answer}",
                },
            ],
            response_format=AnswerEval,
        )
        eval_result = result.choices[0].message.parsed

        self.memory.add_turn(
            "question", question, {"question_idx": question_idx}
        )
        self.memory.add_turn(
            "answer", answer, {"question_idx": question_idx}
        )
        self.memory.add_turn(
            "evaluation",
            f"Score: {eval_result.score}/10. Feedback: {eval_result.feedback}",
            {"question_idx": question_idx, "score": eval_result.score},
        )

        if self.memory.needs_summarization():
            self.memory.summarize_old_turns(self._summarize)

        return eval_result

    def generate_summary(self, topic: str) -> FinalEval:
        context = self.memory.get_context()
        result = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert interviewer creating a summary report "
                        "for a recruiter. Analyze the candidate's performance "
                        "across all questions. Identify specific subtopics the "
                        "candidate knows well (strengths) and specific subtopics "
                        "they lack or performed poorly on (weaknesses). Provide "
                        "an overall summary of their knowledge level. Respond "
                        "with a JSON object containing 'strengths' (list of strings), "
                        "'weaknesses' (list of strings), and 'summary' (string)."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Topic: {topic}\n\nFull interview conversation:\n{context}\n\n"
                        "Provide a detailed summary of the candidate's knowledge, "
                        "listing specific strengths and weaknesses."
                    ),
                },
            ],
            response_format=FinalEval,
        )
        return result.choices[0].message.parsed

    def _summarize(self, text: str) -> str:
        result = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the following interview conversation, "
                        "preserving key patterns about the candidate's strengths, "
                        "weaknesses, and score trajectory. Keep it concise "
                        "(2-3 sentences)."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        return result.choices[0].message.content or ""

    def to_dict(self) -> dict:
        return self.memory.to_dict()
