"""
LLM service for Gemini with mock fallback and simple file cache.
"""
import hashlib
import json
import os
import traceback
from pathlib import Path
from typing import List, Dict, Optional

import google.generativeai as genai


class LLMService:
    """
    Gemini facade with:
    - model selection
    - basic params (temp/top_p/top_k/max_tokens/timeout)
    - file cache
    - mock fallback if no API key
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        cache_dir: str = "data/cache/llm",
        use_mock: bool = False,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.params = {
            "temperature": float(os.getenv("GEMINI_TEMP", temperature or 0.3)),
            "top_p": float(os.getenv("GEMINI_TOP_P", top_p or 0.9)),
            "top_k": int(os.getenv("GEMINI_TOP_K", top_k or 40)),
            "max_output_tokens": int(os.getenv("GEMINI_MAX_TOKENS", max_tokens or 1024)),
        }
        self.timeout = int(os.getenv("GEMINI_TIMEOUT", timeout or 15))
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.use_mock = use_mock or not self.api_key
        self.client = None
        self.last_raw: Optional[str] = None
        if not self.use_mock:
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model_name)

    # --- High-level tasks ---
    def summarize(self, title: str, text: str) -> str:
        prompt = f"Summarize concisely:\nTitle: {title}\nText: {text}"
        if self.use_mock:
            return f"{title} — summarized (mock)."
        return self._run(prompt)

    def make_bullets(self, title: str, text: str, max_points: int = 4) -> List[str]:
        prompt = f"Create up to {max_points} concise bullets for the story:\nTitle: {title}\nText: {text}"
        if self.use_mock:
            return [f"Key point {i+1} about {title} (mock)" for i in range(max_points)]
        resp = self._run(prompt)
        return self._split_lines(resp, max_points)

    def extract_domains(self, text: str) -> List[str]:
        prompt = "Identify 1-3 domains/categories relevant to the text. Return as comma-separated short ids.\n" + text
        if self.use_mock:
            return ["domain_misc"]
        resp = self._run(prompt)
        return [d.strip() for d in resp.split(",") if d.strip()]

    def extract_events(self, text: str) -> List[Dict]:
        prompt = (
            "Extract key events with fields: event_type (fact/opinion), title, description. "
            "Return as short bullet-style lines."
        )
        if self.use_mock:
            return [{
                "event_type": "fact",
                "title": text[:60] + "...",
                "description": text[:120] + "...",
            }]
        resp = self._run(f"{prompt}\n{text}")
        events = []
        for line in resp.splitlines():
            line = line.strip("-• ").strip()
            if not line:
                continue
            events.append({
                "event_type": "fact",
                "title": line[:80],
                "description": line
            })
        return events

    def extract_actors(self, text: str) -> List[Dict]:
        if self.use_mock:
            return [
                {"name": "Acme Corp", "type": "organization", "confidence": 0.82},
                {"name": "John Doe", "type": "person", "confidence": 0.76},
            ]

        def _map_type(t: Optional[str]) -> str:
            allowed = {"person", "company", "country", "organization", "government", "structure", "event"}
            if not t:
                return "organization"
            t_low = str(t).lower()
            if t_low in allowed:
                return t_low
            # heuristic: map 'other' and unknown to organization
            return "organization"

        prompt = (
            "Extract named entities (actors) from the text. "
            "Return JSON array; each item: {\"name\": string, \"type\": \"person|organization|location|other\", \"confidence\": number 0-1}. "
            "Deduplicate, keep top 8 most relevant, concise names.\n"
            f"Text:\n{text}"
        )
        raw = self._run(prompt)
        self.last_raw = raw
        data = self._parse_json_array(raw)
        if not isinstance(data, list):
            data = []

        normalized = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            ent_type = _map_type(item.get("type"))
            conf = item.get("confidence")
            try:
                conf_val = float(conf) if conf is not None else 0.5
            except Exception:
                conf_val = 0.5
            normalized.append({
                "name": str(name).strip(),
                "type": ent_type,
                "confidence": conf_val
            })
        return normalized

    # --- Internal helpers ---
    def _hash(self, prompt: str, model: str, params: Dict) -> str:
        payload = json.dumps({"prompt": prompt, "model": model, "params": params}, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _strip_code_fences(self, text: str) -> str:
        if not text:
            return text
        t = text.strip()
        if t.startswith("```"):
            # remove leading fence ```lang (optional)
            newline_pos = t.find("\n")
            if newline_pos != -1:
                t = t[newline_pos + 1 :]
            # remove trailing fence if present
            if t.endswith("```"):
                t = t[: -3]
        return t.strip()

    def _parse_json_array(self, raw: str):
        cleaned = self._strip_code_fences(raw)
        for candidate in (cleaned, raw):
            try:
                parsed = json.loads(candidate)
                return parsed
            except Exception:
                continue
        return None

    def _cache_get(self, key: str) -> Optional[str]:
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            try:
                return json.loads(path.read_text()).get("text")
            except Exception:
                return None
        return None

    def _cache_set(self, key: str, text: str):
        path = self.cache_dir / f"{key}.json"
        try:
            path.write_text(json.dumps({"text": text}, ensure_ascii=False))
        except Exception:
            pass

    def _run(self, prompt: str, model: Optional[str] = None, **overrides) -> str:
        mdl = model or self.model_name
        params = self.params.copy()
        params.update({k: v for k, v in overrides.items() if v is not None})

        cache_key = self._hash(prompt, mdl, params)
        cached = self._cache_get(cache_key)
        if cached:
            self.last_raw = cached
            return cached

        if self.use_mock or not self.client:
            text = f"[mock response] {prompt[:80]}..."
            self._cache_set(cache_key, text)
            self.last_raw = text
            return text

        try:
            client = genai.GenerativeModel(mdl)
            response = client.generate_content(
                prompt,
                generation_config=params,
                request_options={"timeout": self.timeout}
            )
            text = getattr(response, "text", None) or ""
            self._cache_set(cache_key, text)
            self.last_raw = text
            return text
        except Exception as e:
            # store error text for debug
            self.last_raw = f"LLM error: {e}\n{traceback.format_exc()}"
            raise

    def _split_lines(self, text: str, limit: int) -> List[str]:
        lines = [l.strip("-• ").strip() for l in text.splitlines() if l.strip()]
        return lines[:limit] or [text[:80]]

