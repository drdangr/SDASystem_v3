import importlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.services.llm_service import LLMService


@dataclass
class LLMProfile:
    id: str
    label: str
    provider: str
    model: str
    temperature: float = 0.3
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 1024
    timeout: int = 15

    def to_params(self) -> Dict[str, Any]:
        return {
            "model_name": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }


@dataclass
class ServiceConfig:
    id: str
    label: str
    description: str
    impl: str
    default_profile_id: str
    params: Dict[str, Any]


class ServiceRegistry:
    """
    Реестр LLM-сервисов, читаемый из JSON-конфига.
    Поддерживает хот-релоад через проверку mtime.
    """

    def __init__(self, config_path: str = "config/llm_services.json", auto_reload: bool = True):
        self.config_path = Path(config_path)
        self.auto_reload = auto_reload
        self._services: Dict[str, ServiceConfig] = {}
        self._profiles: Dict[str, LLMProfile] = {}
        self._mtime: Optional[float] = None
        self._raw_config: Dict[str, Any] = {}
        self.reload()

    # --- Public API ---
    def reload(self) -> None:
        """Force reload config from disk."""
        data = self._read_config()
        self._raw_config = data
        self._load_profiles(data.get("profiles", []))
        self._load_services(data.get("services", []))
        self._mtime = self._current_mtime()

    def list_services(self) -> List[ServiceConfig]:
        self._maybe_reload()
        return list(self._services.values())

    def list_profiles(self) -> List[LLMProfile]:
        self._maybe_reload()
        return list(self._profiles.values())

    def get_service(self, service_id: str) -> Optional[ServiceConfig]:
        self._maybe_reload()
        return self._services.get(service_id)

    def get_profile(self, profile_id: str) -> Optional[LLMProfile]:
        self._maybe_reload()
        return self._profiles.get(profile_id)

    def update_service(self, service_id: str, profile_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> ServiceConfig:
        """
        Update service config (profile/params) and persist to JSON.
        """
        self._maybe_reload()
        cfg = self._services.get(service_id)
        if not cfg:
            raise ValueError(f"Service '{service_id}' not registered")
        if profile_id:
            if profile_id not in self._profiles:
                raise ValueError(f"Profile '{profile_id}' not found")
            cfg.default_profile_id = profile_id
        if params is not None:
            cfg.params = params
        # persist
        self._persist()
        return cfg

    def build_llm(self, profile_id: str, use_mock: bool = False) -> LLMService:
        """
        Построить LLMService на основе профиля (параметры перекрываются env).
        """
        profile = self.get_profile(profile_id)
        if not profile:
            raise ValueError(f"LLM profile '{profile_id}' not found")
        params = profile.to_params()
        return LLMService(
            api_key=os.getenv("GEMINI_API_KEY"),
            model_name=params.get("model_name"),
            temperature=params.get("temperature"),
            top_p=params.get("top_p"),
            top_k=params.get("top_k"),
            max_tokens=params.get("max_tokens"),
            timeout=params.get("timeout"),
            use_mock=use_mock,
        )

    def instantiate_service(self, service_id: str):
        """
        Создать экземпляр сервиса по его impl пути.
        impl формат: 'module.submodule:ClassName'
        """
        cfg = self.get_service(service_id)
        if not cfg:
            raise ValueError(f"Service '{service_id}' not registered")

        module_path, class_name = self._split_impl(cfg.impl)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls()

    # --- Internal ---
    def _maybe_reload(self):
        if not self.auto_reload:
            return
        current = self._current_mtime()
        if self._mtime is None or (current and current > self._mtime):
            self.reload()

    def _read_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")
        with self.config_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_profiles(self, items: List[Dict[str, Any]]):
        self._profiles = {}
        for item in items:
            profile = LLMProfile(**item)
            self._profiles[profile.id] = profile

    def _load_services(self, items: List[Dict[str, Any]]):
        self._services = {}
        for item in items:
            params = item.get("params") or {}
            cfg = ServiceConfig(
                id=item["id"],
                label=item.get("label", item["id"]),
                description=item.get("description", ""),
                impl=item["impl"],
                default_profile_id=item["default_profile_id"],
                params=params,
            )
            self._services[cfg.id] = cfg

    def _current_mtime(self) -> Optional[float]:
        if not self.config_path.exists():
            return None
        return self.config_path.stat().st_mtime

    def _split_impl(self, impl: str) -> Tuple[str, str]:
        if ":" not in impl:
            raise ValueError(f"Invalid impl '{impl}', expected format 'module:Class'")
        module_path, class_name = impl.split(":", 1)
        return module_path, class_name

    def _persist(self) -> None:
        """
        Persist current profiles/services to JSON (human-readable).
        """
        data = {
            "profiles": [asdict(p) for p in self._profiles.values()],
            "services": [
                {
                    "id": s.id,
                    "label": s.label,
                    "description": s.description,
                    "impl": s.impl,
                    "default_profile_id": s.default_profile_id,
                    "params": s.params,
                }
                for s in self._services.values()
            ],
        }
        with self.config_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._raw_config = data
        self._mtime = self._current_mtime()

