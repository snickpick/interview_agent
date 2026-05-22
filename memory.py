from dataclasses import dataclass, field, asdict
from typing import Callable, Optional


@dataclass
class MemoryTurn:
    role: str
    content: str
    metadata: dict = field(default_factory=dict)


class InterviewMemory:
    def __init__(self, total_questions: int = 10):
        self.total_questions = total_questions
        self.turns: list[MemoryTurn] = []
        self._summary: Optional[str] = None
        self._configure_tier()

    def _configure_tier(self):
        if self.total_questions >= 150:
            self.tier = 3
            self.window_size = 40
        elif self.total_questions >= 50:
            self.tier = 2
            self.window_size = 40
        else:
            self.tier = 1
            self.window_size = 0

    def add_turn(self, role: str, content: str, metadata: Optional[dict] = None):
        self.turns.append(
            MemoryTurn(role=role, content=content, metadata=metadata or {})
        )

    def get_context(self) -> str:
        parts = []
        if self._summary:
            parts.append(f"[Summary of earlier conversation]:\n{self._summary}\n")

        if self.tier >= 2 and len(self.turns) > self.window_size:
            window = self.turns[-self.window_size :]
        else:
            window = self.turns

        for turn in window:
            label = turn.role.capitalize()
            meta = ""
            if turn.metadata.get("question_idx") is not None:
                meta = f" (Q{turn.metadata['question_idx'] + 1}"
                if turn.metadata.get("score") is not None:
                    meta += f", score: {turn.metadata['score']}/10"
                meta += ")"
            elif turn.role == "evaluation":
                idx = turn.metadata.get("question_idx")
                score = turn.metadata.get("score")
                if idx is not None:
                    meta = f" (Q{idx + 1}"
                    if score is not None:
                        meta += f", score: {score}/10"
                    meta += ")"
            parts.append(f"[{label}{meta}]: {turn.content}")

        return "\n".join(parts)

    def needs_summarization(self) -> bool:
        return (
            self.tier >= 3
            and self._summary is None
            and len(self.turns) > self.window_size * 2
        )

    def summarize_old_turns(self, summarizer_fn: Callable[[str], str]):
        if len(self.turns) <= self.window_size:
            return
        old_turns = self.turns[: -self.window_size]
        text = "\n".join(
            f"{t.role.upper()}: {t.content}"
            + (f" (score: {t.metadata.get('score', '')}/10)" if t.metadata.get("score") is not None else "")
            for t in old_turns
        )
        self._summary = summarizer_fn(text)

    def to_dict(self) -> dict:
        return {
            "total_questions": self.total_questions,
            "turns": [asdict(t) for t in self.turns],
            "summary": self._summary,
        }

    @classmethod
    def from_dict(cls, data: dict):
        memory = cls(total_questions=data.get("total_questions", 10))
        memory.turns = [MemoryTurn(**t) for t in data.get("turns", [])]
        memory._summary = data.get("summary")
        memory._configure_tier()
        return memory
