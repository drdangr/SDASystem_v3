from typing import Any, Dict

from backend.services.llm_service import LLMService


class ActorsLLMService:
    """
    LLM-бейзлайн для извлечения акторов.
    Использует существующий LLMService.extract_actors.
    """

    service_id = "actors_llm"

    def run(self, llm: LLMService, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = payload.get("text") or ""
        actors = llm.extract_actors(text)
        return {"actors": actors, "raw": getattr(llm, "last_raw", None)}

