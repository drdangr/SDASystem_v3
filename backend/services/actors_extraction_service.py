"""
Сервис для извлечения акторов (Hybrid spaCy + LLM), обновления графа
и сохранения результатов в data/actors.json и data/news.json.
"""
from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.models.entities import Actor, ActorType, News
from backend.services.ner_spacy_service import create_hybrid_ner_service, HybridNERService
from backend.services.graph_manager import GraphManager
from backend.services.llm_service import LLMService


@dataclass
class InitProgress:
    running: bool = False
    total: int = 0
    processed: int = 0
    message: str = ""
    current_news_id: Optional[str] = None
    current_news_title: Optional[str] = None
    actors_count: int = 0

    def as_dict(self) -> Dict:
        return {
            "running": self.running,
            "total": self.total,
            "processed": self.processed,
            "message": self.message,
            "current_news_id": self.current_news_id,
            "current_news_title": self.current_news_title,
            "actors_count": self.actors_count,
        }


class ActorsExtractionService:
    """
    Управляет извлечением акторов из новостей, обновлением графа и файлов данных.
    """

    def __init__(
        self,
        graph_manager: GraphManager,
        llm_service: LLMService,
        data_dir: Path | str = "data",
        use_spacy: bool = True,
        spacy_model: str = "en_core_web_sm",
    ) -> None:
        self.graph_manager = graph_manager
        self.llm_service = llm_service
        self.data_dir = Path(data_dir)
        self.actors_file = self.data_dir / "actors.json"
        self.news_file = self.data_dir / "news.json"
        self.backup_dir = self.data_dir / "backup"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.backup_file = self.backup_dir / "actors.json.bak"

        # Используем автоматическое определение языка по умолчанию
        # Если spacy_model указан явно - используем его, иначе автоматически выбираем по языку текста
        self.hybrid: HybridNERService = create_hybrid_ner_service(
            llm_service, 
            use_spacy=use_spacy, 
            spacy_model=spacy_model if spacy_model != "en_core_web_sm" else None,  # Если дефолтная - используем автоопределение
            auto_detect_language=True,  # Автоматически определять язык
            prefer_large_models=False  # Использовать средние модели для баланса скорости/качества
        )
        # Прогресс инициализации
        self.progress = InitProgress()

        # Инициализируем gazetteer, если акторы уже загружены
        if self.graph_manager.actors:
            self.hybrid.load_gazetteer(list(self.graph_manager.actors.values()))
            # Привести к канону и восстановить согласованность
            self.deduplicate_actors()
            self._save_actors()
            self._save_news()
            self._update_all_story_top_actors()

    # ------------------------------------------------------------------ #
    # Внутренние утилиты
    # ------------------------------------------------------------------ #
    def _generate_actor_id(self) -> str:
        return f"actor_{uuid.uuid4().hex[:12]}"

    def _build_canonical_index(self) -> Dict[str, str]:
        """
        Создать индекс alias->actor_id для быстрого поиска существующих акторов.
        """
        index: Dict[str, str] = {}
        for actor_id, actor in self.graph_manager.actors.items():
            names = [actor.canonical_name] + [a.get("name", "") for a in actor.aliases]
            for name in names:
                if not name:
                    continue
                index[name.lower()] = actor_id
        return index

    def _backup_actors_file(self) -> None:
        if self.actors_file.exists():
            shutil.copy2(self.actors_file, self.backup_file)

    def _clear_llm_cache(self) -> None:
        cache_dir = getattr(self.llm_service, "cache_dir", None)
        if cache_dir and Path(cache_dir).exists():
            for path in Path(cache_dir).glob("*.json"):
                try:
                    path.unlink()
                except Exception:
                    continue

    def _reset_news_mentions(self, news_id: str) -> None:
        """Удалить существующие связи news<->actors для новости."""
        news_node = f"news_{news_id}"
        if news_node in self.graph_manager.mentions_graph:
            neighbors = list(self.graph_manager.mentions_graph.neighbors(news_node))
            for nb in neighbors:
                if self.graph_manager.mentions_graph.has_edge(news_node, nb):
                    self.graph_manager.mentions_graph.remove_edge(news_node, nb)

    def _add_mentions_edges(self, news_id: str, actor_ids: List[str]) -> None:
        news_node = f"news_{news_id}"
        for actor_id in actor_ids:
            self.graph_manager.mentions_graph.add_edge(
                news_node, f"actor_{actor_id}", news_id=news_id, actor_id=actor_id
            )

    def _news_text(self, news: News) -> str:
        return f"{news.title}\n{news.summary or ''}\n{news.full_text or ''}"

    def _normalize_key(self, name: str) -> str:
        import re
        n = name.lower().strip()
        n = re.sub(r"[^a-z0-9\\s]", "", n)
        n = re.sub(r"^the\\s+", "", n)
        n = " ".join(n.split())
        return n

    def _add_or_get_actor(
        self, name: str, actor_type: str, confidence: Optional[float], canonical_index: Dict[str, str]
    ) -> Actor:
        key = name.lower().strip()
        if key in canonical_index:
            actor_id = canonical_index[key]
            return self.graph_manager.actors[actor_id]

        # Создать нового
        actor = Actor(
            id=self._generate_actor_id(),
            canonical_name=name,
            actor_type=ActorType(actor_type) if actor_type in ActorType._value2member_map_ else actor_type,
            aliases=[],
            metadata={"confidence": confidence} if confidence is not None else {},
        )
        self.graph_manager.add_actor(actor)
        canonical_index[key] = actor.id
        return actor

    def _save_actors(self) -> None:
        actors_list = [a.model_dump() for a in self.graph_manager.actors.values()]
        self.actors_file.parent.mkdir(parents=True, exist_ok=True)
        with self.actors_file.open("w", encoding="utf-8") as f:
            json.dump(actors_list, f, ensure_ascii=False, indent=2, default=str)

    def _save_news(self) -> None:
        news_list = []
        for n in self.graph_manager.news.values():
            data = n.model_dump()
            news_list.append(data)
        self.news_file.parent.mkdir(parents=True, exist_ok=True)
        with self.news_file.open("w", encoding="utf-8") as f:
            json.dump(news_list, f, ensure_ascii=False, indent=2, default=str)

    def _update_all_story_top_actors(self, top_n: int = 5) -> None:
        for sid in list(self.graph_manager.stories.keys()):
            self.graph_manager.update_story_top_actors(sid, top_n=top_n)

    def deduplicate_actors(self) -> None:
        """
        Дедупликация акторов: одна каноническая запись, остальные в aliases.
        Обновляет news.mentioned_actors и mentions_graph.
        """
        alias_groups = {
            "European Union": ["eu", "the european union", "european union"],
            "United Nations": ["un", "the united nations", "united nations"],
            "Russia": ["russian", "the russian federation", "russia"],
        }
        blacklist_keys = {"peace negotiations"}

        variant_to_canonical = {}
        for canonical, variants in alias_groups.items():
            for v in variants:
                variant_to_canonical[self._normalize_key(v)] = canonical

        key_to_id: Dict[str, str] = {}
        to_delete: List[str] = []
        old_to_new: Dict[str, str] = {}

        # Первичный проход: выбрать канон по normalize_key
        for actor_id, actor in list(self.graph_manager.actors.items()):
            key_raw = self._normalize_key(actor.canonical_name)
            if key_raw in blacklist_keys:
                to_delete.append(actor_id)
                continue

            target_name = variant_to_canonical.get(key_raw, actor.canonical_name)
            if target_name != actor.canonical_name:
                actor.canonical_name = target_name
            key = self._normalize_key(target_name)
            if not key:
                continue
            if key in key_to_id:
                target_id = key_to_id[key]
                old_to_new[actor_id] = target_id
                # перенести canonical_name как alias
                target = self.graph_manager.actors[target_id]
                existing_aliases = {a.get("name", "").lower() for a in target.aliases}
                if actor.canonical_name.lower() not in existing_aliases:
                    target.aliases.append({"name": actor.canonical_name, "type": "alias"})
                    existing_aliases.add(actor.canonical_name.lower())
                # перенести aliases
                for al in actor.aliases:
                    name = al.get("name")
                    if name and name.lower() not in existing_aliases:
                        target.aliases.append(al)
                        existing_aliases.add(name.lower())
                to_delete.append(actor_id)
            else:
                key_to_id[key] = actor_id

        # Удалить дубликаты из графа
        for actor_id in to_delete:
            self.graph_manager.actors.pop(actor_id, None)
            if actor_id in self.graph_manager.actors_graph:
                self.graph_manager.actors_graph.remove_node(actor_id)

        # Обновить ссылки в новостях
        for news in self.graph_manager.news.values():
            updated_ids = []
            seen = set()
            for aid in news.mentioned_actors:
                new_id = old_to_new.get(aid, aid)
                if new_id not in seen:
                    seen.add(new_id)
                    updated_ids.append(new_id)
            news.mentioned_actors = updated_ids

        # Перестроить mentions_graph
        self.graph_manager.mentions_graph.clear()
        for news in self.graph_manager.news.values():
            for aid in news.mentioned_actors:
                self.graph_manager.mentions_graph.add_edge(
                    f"news_{news.id}", f"actor_{aid}", news_id=news.id, actor_id=aid
                )

        # Обновить top_actors в историях (заменить id, удалить несуществующие)
        for story in self.graph_manager.stories.values():
            mapped = []
            for aid in story.top_actors:
                new_id = old_to_new.get(aid, aid)
                if new_id in self.graph_manager.actors:
                    mapped.append(new_id)
            story.top_actors = mapped

        # Пересчитать топ акторов
        self._update_all_story_top_actors()

    # ------------------------------------------------------------------ #
    # Публичные методы
    # ------------------------------------------------------------------ #
    def clear_all(self, clear_cache: bool = True) -> None:
        """
        Очистить акторов из памяти и файлов. Используется перед полным пересчётом.
        """
        self._backup_actors_file()
        self.graph_manager.actors.clear()
        self.graph_manager.actors_graph.clear()
        self.graph_manager.mentions_graph.clear()

        if self.actors_file.exists():
            try:
                self.actors_file.unlink()
            except Exception:
                pass

        if clear_cache:
            self._clear_llm_cache()

    def load_gazetteer(self) -> None:
        """Загрузить актуальный gazetteer в гибридный сервис."""
        self.hybrid.load_gazetteer(list(self.graph_manager.actors.values()))

    def extract_for_news(self, news: News, low_conf_threshold: float = 0.75) -> Tuple[List[Actor], List[str]]:
        """
        Извлечь акторов для конкретной новости и обновить граф.
        Returns: (новые_акторы, actor_ids_for_news)
        """
        canonical_index = self._build_canonical_index()
        text = self._news_text(news)
        extracted = self.hybrid.extract_actors(
            text,
            use_llm=True,
            use_llm_for_low_confidence=True,
            low_confidence_threshold=low_conf_threshold,
        )

        actor_ids: List[str] = []
        for item in extracted:
            name = item.get("name")
            atype = item.get("type", "organization")
            conf = item.get("confidence")
            if not name:
                continue
            actor = self._add_or_get_actor(name, atype, conf, canonical_index)
            actor_ids.append(actor.id)

        # Обновить новость
        self._reset_news_mentions(news.id)
        news.mentioned_actors = actor_ids
        self._add_mentions_edges(news.id, actor_ids)

        # Обновить топ акторов истории
        if news.story_id:
            self.graph_manager.update_story_top_actors(news.story_id)

        return extracted, actor_ids

    def extract_for_story(self, story_id: str, low_conf_threshold: float = 0.75) -> Dict[str, List[str]]:
        if story_id not in self.graph_manager.stories:
            raise ValueError(f"Story {story_id} not found")
        story = self.graph_manager.stories[story_id]
        result: Dict[str, List[str]] = {}
        for news_id in story.news_ids:
            if news_id in self.graph_manager.news:
                news = self.graph_manager.news[news_id]
                _, ids = self.extract_for_news(news, low_conf_threshold)
                result[news_id] = ids
        self.load_gazetteer()
        self.deduplicate_actors()
        self._save_actors()
        self._save_news()
        self._update_all_story_top_actors()
        return result

    def extract_all(self, low_conf_threshold: float = 0.75) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for news in self.graph_manager.news.values():
            _, ids = self.extract_for_news(news, low_conf_threshold)
            result[news.id] = ids
        self.load_gazetteer()
        self.deduplicate_actors()
        self._save_actors()
        self._save_news()
        self._update_all_story_top_actors()
        return result

    # ------------------------------------------------------------------ #
    # Инициализация системы (используется при отсутствии actors.json)
    # ------------------------------------------------------------------ #
    def start_initialization(self, low_conf_threshold: float = 0.75) -> None:
        if self.progress.running:
            return
        self.progress = InitProgress(running=True, total=len(self.graph_manager.news), processed=0, message="Starting")
        self.clear_all(clear_cache=True)

        canonical_index = {}
        for i, news in enumerate(self.graph_manager.news.values(), start=1):
            self.progress.processed = i
            self.progress.message = f"Extracting actors for news {i}/{self.progress.total}"
            news.mentioned_actors = []
            self.progress.current_news_id = news.id
            self.progress.current_news_title = news.title
            # reuse index for dedup across all news
            text = self._news_text(news)
            try:
                extracted = self.hybrid.extract_actors(
                    text,
                    use_llm=True,
                    use_llm_for_low_confidence=True,
                    low_confidence_threshold=low_conf_threshold,
                )
            except Exception as e:
                # Fallback: spaCy-only if LLM quota or other errors
                try:
                    extracted = self.hybrid.extract_actors(
                        text,
                        use_llm=False,
                        use_llm_for_low_confidence=False,
                        low_confidence_threshold=low_conf_threshold,
                    )
                    self.progress.message = f"LLM fallback -> spaCy for news {i}"
                except Exception:
                    self.progress.message = f"Failed on news {news.id}: {e}"
                    continue
            for item in extracted:
                name = item.get("name")
                atype = item.get("type", "organization")
                conf = item.get("confidence")
                if not name:
                    continue
                actor = self._add_or_get_actor(name, atype, conf, canonical_index)
                news.mentioned_actors.append(actor.id)
            self._reset_news_mentions(news.id)
            self._add_mentions_edges(news.id, news.mentioned_actors)
            self.progress.actors_count = len(self.graph_manager.actors)

        self.deduplicate_actors()
        self.load_gazetteer()
        self._save_actors()
        self._save_news()
        self.progress.message = "Completed"
        self.progress.running = False

    def get_status(self) -> Dict:
        actors_count = len(self.graph_manager.actors)
        return {
            "initialized": actors_count > 0,
            "actors_count": actors_count,
            "news_count": len(self.graph_manager.news),
            "progress": self.progress.as_dict(),
        }

