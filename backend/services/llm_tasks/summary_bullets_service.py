from dataclasses import dataclass
from typing import Any, Dict

from backend.services.llm_service import LLMService


@dataclass
class SummaryBulletsInput:
    title: str
    text: str
    max_points: int = 4


class SummaryBulletsService:
    """
    Объединённый сервис саммари + буллетов.
    Предполагается регистрация через ServiceRegistry.
    """

    service_id = "summary_bullets"

    def run(self, llm: LLMService, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = SummaryBulletsInput(
            title=payload.get("title") or "",
            text=payload.get("text") or "",
            max_points=int(payload.get("max_points") or 4),
        )
        summary = llm.summarize(data.title, data.text)
        bullets = llm.make_bullets(data.title, data.text, max_points=data.max_points)
        return {"summary": summary, "bullets": bullets}

