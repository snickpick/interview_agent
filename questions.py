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


def generate_questions(client, topic):
    result = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an expert technical interviewer. Generate 10 interview questions about the given topic. Cover basic, intermediate, and advanced concepts. Questions should test understanding, not just memorization. Return them as a JSON object with a 'questions' key containing an array of 10 strings.",
            },
            {
                "role": "user",
                "content": f"Generate 10 interview questions about: {topic}",
            },
        ],
        response_format=QuestionList,
    )
    return result.choices[0].message.parsed.questions


def evaluate_answer(client, question, answer):
    result = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an expert interviewer evaluating a candidate's answer. Score from 0-10 based on accuracy, completeness, clarity, and depth. Be strict - a perfect score of 10 means the answer is comprehensive and flawless. Provide brief constructive feedback (1-2 sentences). Respond with a JSON object containing 'score' (integer 0-10) and 'feedback' (string).",
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nAnswer: {answer}",
            },
        ],
        response_format=AnswerEval,
    )
    return result.choices[0].message.parsed


def generate_summary(client, topic, qa_pairs):
    pairs_text = "\n".join(
        [
            f"Q: {q}\nA: {a}\nScore: {s}/10\nFeedback: {f}"
            for q, a, s, f in qa_pairs
        ]
    )
    result = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an expert interviewer creating a summary report for a recruiter. Analyze the candidate's performance across all questions. Identify specific subtopics the candidate knows well (strengths) and specific subtopics they lack or performed poorly on (weaknesses). Provide an overall summary of their knowledge level. Respond with a JSON object containing 'strengths' (list of strings), 'weaknesses' (list of strings), and 'summary' (string).",
            },
            {
                "role": "user",
                "content": f"Topic: {topic}\n\nInterview Q&A:\n{pairs_text}\n\nProvide a detailed summary of the candidate's knowledge, listing specific strengths and weaknesses.",
            },
        ],
        response_format=FinalEval,
    )
    return result.choices[0].message.parsed
