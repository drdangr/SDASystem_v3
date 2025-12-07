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
from backend.services.ner_spacy_service import create_hybrid_ner_service, HybridNERService, detect_language
from backend.services.graph_manager import GraphManager
from backend.services.llm_service import LLMService
from backend.services.actor_canonicalization_service import ActorCanonicalizationService


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

    BLACKLIST_KEYS = {
        "peace negotiations", "negotiations", "conflict", "war", "peace", "summit", "meeting"
    }

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
        
        # Сервис канонизации акторов
        self.canonicalization_service = ActorCanonicalizationService(
            use_wikidata=True,
            use_lemmatization=True,
            prefer_large_models=False
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
        # Разрешаем буквы (включая кириллицу), цифры, пробелы
        # Явно добавляем диапазон кириллицы для надежности
        n = re.sub(r"[^\w\s\u0400-\u04FFёЁ]", "", n)
        n = re.sub(r"^the\\s+", "", n)
        n = " ".join(n.split())
        return n

    def _add_or_get_actor(
        self, name: str, actor_type: str, confidence: Optional[float], canonical_index: Dict[str, str]
    ) -> Actor:
        """Старый метод для обратной совместимости"""
        return self._add_or_get_actor_with_canonicalization(
            name, actor_type, confidence, canonical_index
        )
    
    def _add_or_get_actor_with_canonicalization(
        self,
        canonical_name: str,
        actor_type: str,
        confidence: Optional[float],
        canonical_index: Dict[str, str],
        wikidata_qid: Optional[str] = None,
        aliases: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict] = None
    ) -> Actor:
        """
        Добавить или получить актора с поддержкой канонизации.
        
        Args:
            canonical_name: Каноническое имя актора
            actor_type: Тип актора
            confidence: Уверенность
            canonical_index: Индекс для быстрого поиска
            wikidata_qid: QID из Wikidata (если есть)
            aliases: Список алиасов
            metadata: Дополнительные метаданные
        """
        # Сначала проверяем по QID (самый надежный способ)
        if wikidata_qid:
            for actor_id, actor in self.graph_manager.actors.items():
                if actor.wikidata_qid == wikidata_qid:
                    # Обновляем алиасы и метаданные если нужно
                    self._update_actor_aliases(actor, aliases or [])
                    self._update_actor_metadata(actor, metadata or {})
                    return actor
        
        # Проверяем по каноническому имени
        key = canonical_name.lower().strip()
        if key in canonical_index:
            actor_id = canonical_index[key]
            actor = self.graph_manager.actors[actor_id]
            # Обновляем QID если его еще нет
            if wikidata_qid and not actor.wikidata_qid:
                actor.wikidata_qid = wikidata_qid
            # Обновляем алиасы и метаданные
            self._update_actor_aliases(actor, aliases or [])
            self._update_actor_metadata(actor, metadata or {})
            return actor
        
        # Проверяем по алиасам
        if aliases:
            for alias_entry in aliases:
                alias_name = alias_entry.get("name", "").lower().strip()
                if alias_name in canonical_index:
                    actor_id = canonical_index[alias_name]
                    actor = self.graph_manager.actors[actor_id]
                    # Обновляем каноническое имя если оно лучше
                    if canonical_name != actor.canonical_name:
                        # Добавляем старое каноническое имя как алиас
                        self._add_alias_if_not_exists(actor, actor.canonical_name, "canonical")
                        actor.canonical_name = canonical_name
                    # Обновляем остальное
                    if wikidata_qid:
                        actor.wikidata_qid = wikidata_qid
                    self._update_actor_aliases(actor, aliases)
                    self._update_actor_metadata(actor, metadata or {})
                    canonical_index[key] = actor.id
                    return actor

        # Создать нового актора
        actor_metadata = metadata.copy() if metadata else {}
        if confidence is not None:
            actor_metadata["confidence"] = confidence
        
        actor = Actor(
            id=self._generate_actor_id(),
            canonical_name=canonical_name,
            actor_type=ActorType(actor_type) if actor_type in ActorType._value2member_map_ else actor_type,
            aliases=aliases.copy() if aliases else [],
            wikidata_qid=wikidata_qid,
            metadata=actor_metadata,
        )
        self.graph_manager.add_actor(actor)
        canonical_index[key] = actor.id
        
        # Добавляем алиасы в индекс
        if aliases:
            for alias_entry in aliases:
                alias_name = alias_entry.get("name", "").lower().strip()
                if alias_name and alias_name != key:
                    canonical_index[alias_name] = actor.id
        
        return actor
    
    def _update_actor_aliases(self, actor: Actor, new_aliases: List[Dict[str, str]]):
        """Обновить алиасы актора, добавив новые если их еще нет"""
        existing_aliases = {a.get("name", "").lower() for a in actor.aliases}
        
        for alias_entry in new_aliases:
            alias_name = alias_entry.get("name", "")
            if alias_name and alias_name.lower() not in existing_aliases:
                actor.aliases.append(alias_entry)
                existing_aliases.add(alias_name.lower())
    
    def _add_alias_if_not_exists(self, actor: Actor, alias_name: str, alias_type: str = "alias"):
        """Добавить алиас если его еще нет"""
        existing_aliases = {a.get("name", "").lower() for a in actor.aliases}
        if alias_name.lower() not in existing_aliases:
            actor.aliases.append({
                "name": alias_name,
                "type": alias_type
            })
    
    def _update_actor_metadata(self, actor: Actor, new_metadata: Dict):
        """Обновить метаданные актора, объединив с существующими"""
        actor.metadata.update(new_metadata)

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

    def _find_merge_candidates(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        Найти кандидатов на слияние.
        Returns:
            Tuple[qid_groups, key_groups]: Группы по QID и по нормализованному имени.
        """
        qid_to_actors: Dict[str, List[str]] = {}
        key_to_actors: Dict[str, List[str]] = {}
        
        for actor_id, actor in self.graph_manager.actors.items():
            # 1. Группировка по QID
            if actor.wikidata_qid:
                if actor.wikidata_qid not in qid_to_actors:
                    qid_to_actors[actor.wikidata_qid] = []
                qid_to_actors[actor.wikidata_qid].append(actor_id)
            
            # 2. Группировка по нормализованному имени (для тех, у кого нет QID или как вторичный критерий)
            key = self._normalize_key(actor.canonical_name)
            if key and key not in self.BLACKLIST_KEYS:
                if key not in key_to_actors:
                    key_to_actors[key] = []
                key_to_actors[key].append(actor_id)
                
        return qid_to_actors, key_to_actors

    def _merge_actor_groups(self, actor_groups: List[List[str]]) -> Tuple[Dict[str, str], List[str]]:
        """
        Выполнить слияние групп акторов.
        Returns:
            Tuple[old_to_new_map, ids_to_delete]: Маппинг замен и список на удаление.
        """
        old_to_new: Dict[str, str] = {}
        to_delete: List[str] = []
        
        for group in actor_groups:
            if len(group) < 2:
                continue
                
            # Сортируем: сначала те что с QID, потом по длине имени (предпочитаем более полные)
            # Но для простоты берем первого как target, если у него есть QID, или ищем лучшего
            target_id = group[0]
            # Простая эвристика: выбираем актора, у которого есть QID
            for aid in group:
                if self.graph_manager.actors[aid].wikidata_qid:
                    target_id = aid
                    break
            
            target_actor = self.graph_manager.actors[target_id]
            
            for source_id in group:
                if source_id == target_id:
                    continue
                    
                # Проверяем, не был ли этот source_id уже слит (защита от циклов и дублей)
                if source_id in old_to_new:
                    continue
                
                source_actor = self.graph_manager.actors[source_id]
                
                # Логика слияния
                old_to_new[source_id] = target_id
                to_delete.append(source_id)
                
                # 1. Перенос алиасов
                self._update_actor_aliases(target_actor, source_actor.aliases)
                # 2. Имя сливаемого как алиас
                self._add_alias_if_not_exists(target_actor, source_actor.canonical_name, "merged")
                # 3. QID
                if source_actor.wikidata_qid and not target_actor.wikidata_qid:
                    target_actor.wikidata_qid = source_actor.wikidata_qid
                # 4. Metadata
                self._update_actor_metadata(target_actor, source_actor.metadata)
        
        return old_to_new, to_delete

    def deduplicate_actors(self) -> None:
        """
        Дедупликация акторов: одна каноническая запись, остальные в aliases.
        Использует QID из Wikidata и нормализованные имена.
        """
        qid_groups, key_groups = self._find_merge_candidates()
        
        # Собираем все группы для слияния в один список
        # Важно: сначала обрабатываем группы по QID, так как они точнее
        all_groups = list(qid_groups.values())
        
        # Затем добавляем группы по имени, но нужно быть осторожным, чтобы не слить то, что уже слито
        # В текущей реализации _merge_actor_groups проверяет source_id in old_to_new, так что это безопасно
        all_groups.extend(list(key_groups.values()))
        
        # Выполняем слияние
        old_to_new, to_delete = self._merge_actor_groups(all_groups)
        
        if not to_delete:
            return

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
                # Если ID был удален, но не замаплен (странная ситуация, но возможна), пропускаем
                if new_id in to_delete and new_id not in old_to_new:
                    continue
                # Берем финальный ID (на случай цепочек слияний a->b->c)
                final_id = new_id
                while final_id in old_to_new:
                    final_id = old_to_new[final_id]
                
                if final_id not in seen and final_id not in to_delete:
                    if final_id in self.graph_manager.actors: # Проверка существования
                        seen.add(final_id)
                        updated_ids.append(final_id)
            news.mentioned_actors = updated_ids

        # Перестроить mentions_graph (чистый способ)
        self.graph_manager.mentions_graph.clear()
        for news in self.graph_manager.news.values():
            for aid in news.mentioned_actors:
                if aid in self.graph_manager.actors:
                    self.graph_manager.mentions_graph.add_edge(
                        f"news_{news.id}", f"actor_{aid}", news_id=news.id, actor_id=aid
                    )

        # Обновить top_actors в историях
        for story in self.graph_manager.stories.values():
            mapped = []
            seen = set()
            for aid in story.top_actors:
                final_id = old_to_new.get(aid, aid)
                while final_id in old_to_new:
                    final_id = old_to_new[final_id]
                
                if final_id in self.graph_manager.actors and final_id not in seen:
                    mapped.append(final_id)
                    seen.add(final_id)
            story.top_actors = mapped

        # Пересчитать топ акторов для всех историй
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

        # Определяем язык текста для подсказки канонизатору
        news_language = detect_language(text)

        # Канонизировать извлеченных акторов перед добавлением в граф
        canonicalized = self.canonicalization_service.canonicalize_batch(extracted, default_language=news_language)

        actor_ids: List[str] = []
        for item in canonicalized:
            # Используем каноническое имя вместо оригинального
            canonical_name = item.get("canonical_name") or item.get("name")
            atype = item.get("type", "organization")
            conf = item.get("confidence")
            wikidata_qid = item.get("wikidata_qid")
            aliases = item.get("aliases", [])
            metadata = item.get("metadata", {})
            
            if not canonical_name:
                continue
            
            # Проверяем, существует ли актор с таким QID или каноническим именем
            actor = self._add_or_get_actor_with_canonicalization(
                canonical_name, 
                atype, 
                conf, 
                canonical_index,
                wikidata_qid=wikidata_qid,
                aliases=aliases,
                metadata=metadata
            )
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
        print("DEBUG: extract_all called")
        # Force update status immediately
        self.progress.message = "Extracting all actors..."
        self.progress.total = len(self.graph_manager.news)
        self.progress.processed = 0
        self.progress.running = True
        
        result: Dict[str, List[str]] = {}
        
        canonical_index = self._build_canonical_index()
        print(f"DEBUG: Starting loop over {len(self.graph_manager.news)} news items")
        
        for i, news in enumerate(list(self.graph_manager.news.values()), start=1):
            print(f"DEBUG: Processing news {i}/{self.progress.total}: {news.id}")
            self.progress.processed = i
            self.progress.message = f"Extracting actors for news {i}/{self.progress.total}"
            self.progress.current_news_id = news.id
            self.progress.current_news_title = news.title
            
            try:
                _, ids = self.extract_for_news(news, low_conf_threshold)
                result[news.id] = ids
            except Exception as e:
                print(f"Error extracting for news {news.id}: {e}")
            
            self.progress.actors_count = len(self.graph_manager.actors)

        self.load_gazetteer()
        self.deduplicate_actors()
        self._save_actors()
        self._save_news()
        self._update_all_story_top_actors()
        
        self.progress.message = "Completed"
        self.progress.running = False
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

