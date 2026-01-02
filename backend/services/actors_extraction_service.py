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
from backend.services.ner_spacy_service import detect_language
from backend.services.google_ner_service import GoogleNERService
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

        # Используем GoogleNERService (Gemini) как основной сервис
        self.hybrid = GoogleNERService(llm_service)
        
        # Сервис канонизации акторов (Wikidata)
        # Оставляем его для получения QID и метаданных, но полагаемся на имя от LLM
        self.canonicalization_service = ActorCanonicalizationService(
            use_wikidata=True,
            use_lemmatization=False, # LLM уже лемматизирует
            prefer_large_models=False
        )
        
        # Прогресс инициализации
        self.progress = InitProgress()

        # Инициализируем gazetteer, если акторы уже загружены
        # (GoogleNERService не использует gazetteer напрямую, но мы можем загрузить его если понадобится позже)
        if self.graph_manager.actors:
            # self.hybrid.load_gazetteer(list(self.graph_manager.actors.values()))
            # Привести к канону и восстановить согласованность
            self.deduplicate_actors()
            # Note: _save_actors() and _save_news() are no-ops - data is saved via GraphManager
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

    def _has_cyrillic(self, s: str) -> bool:
        if not s:
            return False
        import re
        return bool(re.search(r"[\u0400-\u04FF]", s))

    def _pick_best_latin_alias(self, actor: Actor) -> Optional[str]:
        """
        Выбрать лучший вариант имени в латинице из canonical_name/aliases.
        Эвристика: предпочитаем более длинные (обычно полные имена), без кириллицы.
        """
        candidates: List[str] = []
        if actor.canonical_name and not self._has_cyrillic(actor.canonical_name):
            candidates.append(actor.canonical_name)
        for a in actor.aliases or []:
            nm = (a or {}).get("name")
            if nm and not self._has_cyrillic(nm):
                candidates.append(nm)
        if not candidates:
            return None
        # длиннее = лучше, если равны — лексикографически стабильно
        candidates = sorted(set(candidates), key=lambda x: (-len(x), x))
        return candidates[0]

    def _late_latinize_actor_names(self) -> None:
        """
        Пост-обработка: если у актора canonical_name в кириллице,
        но уже есть латинский алиас (или Wikidata дала латинский label),
        то переносим латиницу в canonical_name, а старое имя оставляем алиасом.
        """
        for actor in self.graph_manager.actors.values():
            if not actor.canonical_name or not self._has_cyrillic(actor.canonical_name):
                continue
            best = self._pick_best_latin_alias(actor)
            if not best:
                continue
            if best == actor.canonical_name:
                continue
            # сохранить старое имя как алиас и переключить canonical_name
            self._add_alias_if_not_exists(actor, actor.canonical_name, "canonical_prev")
            actor.canonical_name = best

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
            actor = self.graph_manager.get_actor(actor_id)
            if not actor:
                return None
            # Обновляем QID если его еще нет
            if wikidata_qid and not actor.wikidata_qid:
                actor.wikidata_qid = wikidata_qid
            # Обновляем алиасы и метаданные
            self._update_actor_aliases(actor, aliases or [])
            self._update_actor_metadata(actor, metadata or {})
            # Сохраняем изменения в БД
            self.graph_manager.add_actor(actor)
            return actor
        
        # Проверяем по алиасам
        if aliases:
            for alias_entry in aliases:
                alias_name = alias_entry.get("name", "").lower().strip()
                if alias_name in canonical_index:
                    actor_id = canonical_index[alias_name]
                    actor = self.graph_manager.get_actor(actor_id)
                    if not actor:
                        continue
                    # Обновляем каноническое имя если оно лучше
                    if canonical_name != actor.canonical_name:
                        # Добавляем старое каноническое имя как алиас
                        self._add_alias_if_not_exists(actor, actor.canonical_name, "canonical")
                        actor.canonical_name = canonical_name
                    # Обновляем остальное
                    if wikidata_qid:
                        actor.wikidata_qid = wikidata_qid
                    self._update_actor_aliases(actor, aliases)
                    # Сохраняем изменения в БД
                    self.graph_manager.add_actor(actor)
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
        """Save actors to database (via GraphManager)"""
        # Actors are automatically saved to database when added via graph_manager.add_actor()
        # This method is kept for backward compatibility but now does nothing
        # as all saves go through GraphManager -> DatabaseManager
        pass

    def _save_news(self) -> None:
        """Save news to database (via GraphManager)"""
        # News are automatically saved to database when added via graph_manager.add_news()
        # This method is kept for backward compatibility but now does nothing
        # as all saves go through GraphManager -> DatabaseManager
        pass

    def _update_all_story_top_actors(self, top_n: int = 5) -> None:
        for sid in list(self.graph_manager.stories.keys()):
            self.graph_manager.update_story_top_actors(sid, top_n=top_n)

    def _find_merge_candidates(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        Найти кандидатов на слияние.
        Returns:
            Tuple[qid_groups, key_groups]: Группы по QID и по нормализованному имени/алиасам.
        """
        qid_to_actors: Dict[str, List[str]] = {}
        key_to_actors: Dict[str, List[str]] = {}
        
        # Build alias->actor_id index from actors WITH QID (they are authoritative)
        alias_to_authoritative: Dict[str, str] = {}
        for actor_id, actor in self.graph_manager.actors.items():
            if actor.wikidata_qid:
                # Index canonical name
                key = self._normalize_key(actor.canonical_name)
                if key:
                    alias_to_authoritative[key] = actor_id
                # Index all aliases
                for alias_entry in actor.aliases:
                    alias_name = alias_entry.get("name", "")
                    if alias_name:
                        alias_key = self._normalize_key(alias_name)
                        if alias_key:
                            alias_to_authoritative[alias_key] = actor_id
        
        for actor_id, actor in self.graph_manager.actors.items():
            # 1. Группировка по QID
            if actor.wikidata_qid:
                if actor.wikidata_qid not in qid_to_actors:
                    qid_to_actors[actor.wikidata_qid] = []
                qid_to_actors[actor.wikidata_qid].append(actor_id)
            else:
                # 2. Для акторов без QID - проверить совпадение с алиасами авторитетных акторов
                key = self._normalize_key(actor.canonical_name)
                if key and key in alias_to_authoritative:
                    auth_actor_id = alias_to_authoritative[key]
                    # Group this actor with the authoritative one
                    auth_actor = self.graph_manager.get_actor(auth_actor_id)
                    auth_qid = auth_actor.wikidata_qid if auth_actor else None
                    if auth_qid:
                        if auth_qid not in qid_to_actors:
                            qid_to_actors[auth_qid] = []
                        if actor_id not in qid_to_actors[auth_qid]:
                            qid_to_actors[auth_qid].append(actor_id)
                        continue
            
            # 3. Группировка по нормализованному имени (fallback)
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
        updated_target_actors = {}  # Track updated target actors per group
        
        for group in actor_groups:
            if len(group) < 2:
                continue
                
            # Сортируем: сначала те что с QID, потом по длине имени (предпочитаем более полные)
            # Но для простоты берем первого как target, если у него есть QID, или ищем лучшего
            target_id = group[0]
            # Простая эвристика: выбираем актора, у которого есть QID
            for aid in group:
                actor = self.graph_manager.get_actor(aid)
                if actor and actor.wikidata_qid:
                    target_id = aid
                    break
            
            target_actor = self.graph_manager.get_actor(target_id)
            if not target_actor:
                continue
            
            for source_id in group:
                if source_id == target_id:
                    continue
                    
                # Проверяем, не был ли этот source_id уже слит (защита от циклов и дублей)
                if source_id in old_to_new:
                    continue
                
                source_actor = self.graph_manager.get_actor(source_id)
                if not source_actor:
                    continue
                
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
            
            # Сохраняем обновленного target_actor для этой группы
            updated_target_actors[target_id] = target_actor
        
        # Сохраняем все обновленные target_actors в БД
        for target_actor in updated_target_actors.values():
            self.graph_manager.add_actor(target_actor)
        
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

        # Удалить дубликаты из графа (удаление из БД не выполняется для сохранения целостности)
        # Акторы остаются в БД, но ссылки обновляются
        for actor_id in to_delete:
            # Удаляем из кэша и графа
            if actor_id in self.graph_manager._actors_cache:
                del self.graph_manager._actors_cache[actor_id]
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
                    # Проверяем существование актора через БД
                    actor = self.graph_manager.get_actor(final_id)
                    if actor:
                        seen.add(final_id)
                        updated_ids.append(final_id)
            
            if news.mentioned_actors != updated_ids:
                news.mentioned_actors = updated_ids
                # Сохраняем обновленную новость в БД
                self.graph_manager.add_news(news)

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
        # self.hybrid.load_gazetteer(list(self.graph_manager.actors.values()))
        pass

    def extract_for_news(self, news: News, low_conf_threshold: float = 0.75) -> Tuple[List[Actor], List[str]]:
        """
        Извлечь акторов для конкретной новости и обновить граф.
        Returns: (новые_акторы, actor_ids_for_news)
        """
        canonical_index = self._build_canonical_index()
        text = self._news_text(news)
        
        # Основной метод: GoogleNERService (Gemini) — возвращает канонику в латинице.
        extracted = self.hybrid.extract_actors(text)

        # Fallback: иногда LLM возвращает слишком мало сущностей (или только одну).
        # Тогда дополняем результат вторым, более “жадным” промптом (LLMService.extract_actors),
        # чтобы гарантировать покрытие ключевых акторов (Biden/Putin/etc.).
        try:
            if not extracted or len(extracted) < 3:
                fallback = self.llm_service.extract_actors(text) or []
                # Нормализуем формат, чтобы дальше канонизация работала одинаково
                normalized = []
                for a in fallback:
                    if not isinstance(a, dict):
                        continue
                    nm = a.get("name")
                    if not nm:
                        continue
                    normalized.append({
                        "name": nm,
                        "type": a.get("type", "organization"),
                        "confidence": a.get("confidence", 0.7),
                        # original_name отсутствует в этом пути
                    })
                # merge by lowercase name to avoid duplicates
                seen = {str(x.get("name", "")).lower() for x in extracted if isinstance(x, dict)}
                for a in normalized:
                    key = str(a.get("name", "")).lower()
                    if key and key not in seen:
                        extracted.append(a)
                        seen.add(key)
        except Exception:
            # если fallback сломался — продолжаем с тем, что есть
            pass

        # Определяем язык текста для подсказки канонизатору
        news_language = detect_language(text)

        # Канонизировать извлеченных акторов перед добавлением в граф
        # (GoogleNERService уже чистит, но здесь мы ищем QID)
        canonicalized = self.canonicalization_service.canonicalize_batch(extracted, default_language=news_language)

        actor_ids_set: set = set()  # Use set to avoid duplicates
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
            actor_ids_set.add(actor.id)  # Add to set (auto-deduplication)

        # После добавления/обновления акторов пробуем улучшить canonical_name до латиницы
        # (закрывает кейсы “поздней латинизации”, когда латинская форма появляется позже)
        self._late_latinize_actor_names()

        # Convert to list for storage
        actor_ids = list(actor_ids_set)
        
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
        story = self.graph_manager.get_story(story_id)
        if not story:
            raise ValueError(f"Story {story_id} not found")
        result: Dict[str, List[str]] = {}
        for news_id in story.news_ids:
            news = self.graph_manager.get_news(news_id)
            if news:
                _, ids = self.extract_for_news(news, low_conf_threshold)
                result[news_id] = ids
        self.load_gazetteer()
        self.deduplicate_actors()
        self._late_latinize_actor_names()
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
        self._late_latinize_actor_names()
        # Note: Actors and news are saved via GraphManager automatically
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
            self.progress.current_news_id = news.id
            self.progress.current_news_title = news.title
            # reuse index for dedup across all news
            text = self._news_text(news)
            try:
                # Используем новый метод
                extracted = self.hybrid.extract_actors(text)
            except ValueError as e:
                # Ошибка API ключа - логируем и пропускаем эту новость
                error_str = str(e)
                if "API КЛЮЧА" in error_str or "leaked" in error_str.lower():
                    if i == 1:  # Выводим сообщение только один раз
                        print(f"\n⚠️  ВНИМАНИЕ: Обнаружена ошибка API ключа при извлечении акторов.\n")
                    self.progress.message = f"API ключ недействителен (новость {i}/{self.progress.total})"
                else:
                    self.progress.message = f"Failed on news {news.id}: {e}"
                continue
            except Exception as e:
                self.progress.message = f"Failed on news {news.id}: {e}"
                continue
            
            # Use set to avoid duplicates
            actor_ids_set: set = set()
            for item in extracted:
                name = item.get("name")
                atype = item.get("type", "organization")
                conf = item.get("confidence")
                if not name:
                    continue
                actor = self._add_or_get_actor(name, atype, conf, canonical_index)
                actor_ids_set.add(actor.id)
            
            news.mentioned_actors = list(actor_ids_set)
            self._reset_news_mentions(news.id)
            self._add_mentions_edges(news.id, news.mentioned_actors)
            self.progress.actors_count = len(self.graph_manager.actors)

        self.deduplicate_actors()
        self._late_latinize_actor_names()
        self.load_gazetteer()
        # Note: Actors and news are saved via GraphManager automatically
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
