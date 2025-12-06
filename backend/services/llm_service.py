"""
LLM service scaffold.
Supports mock responses for prototype, ready to be wired to real providers.
"""
import os
from typing import List, Dict, Optional


class LLMService:
    """
    Simple LLM facade with mock fallbacks.
    Real provider calls can be added by wiring `self.provider` methods.
    """

    def __init__(self, provider: str = "mock"):
        self.provider = provider or os.getenv("LLM_PROVIDER", "mock")

    # --- High-level tasks ---
    def summarize(self, title: str, text: str) -> str:
        if self.provider == "mock":
            return f"{title} — summarized (mock)."
        return self._not_implemented("summarize")

    def make_bullets(self, title: str, text: str, max_points: int = 4) -> List[str]:
        if self.provider == "mock":
            return [f"Key point {i+1} about {title} (mock)" for i in range(max_points)]
        return self._not_implemented("make_bullets")

    def extract_domains(self, text: str) -> List[str]:
        if self.provider == "mock":
            return ["domain_misc"]
        return self._not_implemented("extract_domains")

    def extract_events(self, text: str) -> List[Dict]:
        if self.provider == "mock":
            return [{
                "event_type": "fact",
                "title": text[:60] + "...",
                "description": text[:120] + "...",
            }]
        return self._not_implemented("extract_events")

    # --- Internal helpers ---
    def _not_implemented(self, method: str):
        raise NotImplementedError(f"LLM provider '{self.provider}' method '{method}' not implemented")

