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
            allowed = {
                "person", "company", "country", "organization", 
                "government", "politician", "int_org", 
                "structure", "event"
            }
            # Synonyms mapping
            synonyms = {
                "human": "person", "man": "person", "woman": "person", "individual": "person", 
                
                # Politician mapping
                "president": "politician", "prime minister": "politician", 
                "minister": "politician", "deputy": "politician",
                "official": "politician", "leader": "politician", 
                "ambassador": "politician", "diplomat": "politician",
                "senator": "politician", "governor": "politician",

                # Government mapping
                "ministry": "government", "department": "government", 
                "council": "government", "parliament": "government",
                "court": "government", "administration": "government",
                "white house": "government", "kremlin": "government",

                # Int Org mapping
                "alliance": "int_org", "union": "int_org",

                "firm": "company", "corporation": "company", "business": "company", "enterprise": "company",
                "nation": "country", 
                "agency": "organization", "association": "organization", "group": "organization", "party": "organization"
            }
            
            if not t:
                return "organization"
            t_low = str(t).lower().strip()
            
            if t_low in allowed:
                return t_low
            
            if t_low in synonyms:
                return synonyms[t_low]
                
            # heuristic: map 'other' and unknown to organization
            return "organization"

        prompt = (
            "Extract ALL named entities (actors) from the text. Classify them into these types:\n"
            "- politician: government officials, presidents, ministers, diplomats (e.g., 'Vladimir Putin', 'Joe Biden')\n"
            "- person: other individuals (non-political)\n"
            "- company: commercial entities (e.g., 'Tesla', 'Gazprom')\n"
            "- country: nations (e.g., 'United States', 'Russia')\n"
            "- government: state bodies, ministries, parliaments (e.g., 'State Department', 'Kremlin')\n"
            "- int_org: international organizations (e.g., 'NATO', 'UN', 'EU')\n"
            "- organization: other organizations, parties, NGOs\n\n"
            "- Also extract indirect mentions: if text says 'US' or 'America', extract 'United States'; "
            "if text says 'EU', extract 'European Union'; if text says 'Putin' or 'President Putin', extract 'Vladimir Putin'\n\n"
            "Return a JSON array. Each item: {\"name\": string, \"type\": \"politician|person|company|country|government|int_org|organization\", \"confidence\": number 0-1}\n"
            "- Use canonical/full names when possible (prefer 'United States' over 'US', 'Vladimir Putin' over 'Putin')\n"
            "- Include both canonical and alias mentions if they appear in text\n"
            "- Deduplicate similar entities (merge 'US' and 'United States' as one)\n"
            "- Keep top 8-10 most relevant actors\n"
            "- confidence: 0.9+ for explicit mentions, 0.7-0.8 for indirect/implied mentions\n\n"
            "Example:\n"
            "Text: 'Putin criticized NATO and the US'\n"
            "Output: [{\"name\": \"Vladimir Putin\", \"type\": \"politician\", \"confidence\": 0.95}, "
            "{\"name\": \"NATO\", \"type\": \"int_org\", \"confidence\": 0.95}, "
            "{\"name\": \"United States\", \"type\": \"country\", \"confidence\": 0.9}]\n\n"
            f"Text:\n{text}"
        )
        raw = self._run(prompt)
        self.last_raw = raw
        
        # Проверка на пустой ответ
        if not raw or raw.strip() == "[empty response]" or len(raw.strip()) < 10:
            # Повторная попытка с упрощенным промптом
            simple_prompt = (
                "Extract named entities from the text. Return JSON array: "
                "[{\"name\": string, \"type\": \"politician|person|company|country|organization\", \"confidence\": 0.9}]. "
                "Extract persons, politicians, companies, countries, organizations mentioned in the text.\n"
                f"Text:\n{text}"
            )
            raw = self._run(simple_prompt, **{"temperature": 0.2})  # Более детерминированный режим
            self.last_raw = raw
        
        data = self._parse_json_array(raw)
        if not isinstance(data, list):
            data = []

        normalized = []
        seen_names = set()  # Для дедупликации
        
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            
            name = str(name).strip()
            name_lower = name.lower()
            
            # Дедупликация (пропускаем если уже видели похожее имя)
            if name_lower in seen_names:
                continue
            
            # Нормализация: приводим к каноническим формам
            normalized_name = self._normalize_actor_name(name)
            
            ent_type = _map_type(item.get("type"))
            
            # Улучшенное определение типа на основе имени
            if ent_type == "organization" and self._looks_like_country(normalized_name):
                ent_type = "country"
            elif ent_type == "organization" and self._looks_like_company(normalized_name):
                ent_type = "company"
            
            conf = item.get("confidence")
            try:
                conf_val = float(conf) if conf is not None else 0.5
            except Exception:
                conf_val = 0.5
            
            normalized.append({
                "name": normalized_name,
                "type": ent_type,
                "confidence": conf_val
            })
            seen_names.add(name_lower)
            seen_names.add(normalized_name.lower())
        
        return normalized
    
    def _normalize_actor_name(self, name: str) -> str:
        """Нормализовать имя актора к канонической форме"""
        name = name.strip()
        name_lower = name.lower()
        
        # Страны - приводим к полным названиям
        country_map = {
            "us": "United States",
            "usa": "United States",
            "u.s.": "United States",
            "u.s.a.": "United States",
            "america": "United States",
            "uk": "United Kingdom",
            "u.k.": "United Kingdom",
            "eu": "European Union",
            "nato": "NATO",
            "who": "World Health Organization",
            "un": "United Nations",
            "оон": "United Nations",
            "россия": "Russia",
            "рф": "Russia",
            "китай": "China",
            "prc": "China",
            "украина": "Ukraine"
        }
        
        if name_lower in country_map:
            return country_map[name_lower]
        
        # Сохраняем оригинальное имя, но очищаем
        return name
    
    def _looks_like_country(self, name: str) -> bool:
        """Эвристика: похоже ли имя на страну"""
        country_indicators = ["united states", "russia", "china", "ukraine", "france", "germany", 
                            "japan", "korea", "india", "brazil", "mexico", "canada", "australia"]
        return any(indicator in name.lower() for indicator in country_indicators)
    
    def _looks_like_company(self, name: str) -> bool:
        """Эвристика: похоже ли имя на компанию"""
        company_indicators = ["inc", "corp", "ltd", "llc", "company", "technologies", "systems"]
        name_lower = name.lower()
        return any(indicator in name_lower for indicator in company_indicators)

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
            print(f"DEBUG: LLM _run using mock. use_mock={self.use_mock}, client={self.client}, api_key_len={len(str(self.api_key)) if self.api_key else 0}")
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
            text = ""
            try:
                text = getattr(response, "text", None) or ""
            except Exception:
                text = ""
            if not text:
                # fallback: concatenate parts from first candidate
                candidates = getattr(response, "candidates", None) or []
                if candidates:
                    parts = getattr(candidates[0], "content", None)
                    if parts and getattr(parts, "parts", None):
                        text = "\n".join([getattr(p, "text", "") or "" for p in parts.parts if getattr(p, "text", "")])
            if not text:
                text = "[empty response]"
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

