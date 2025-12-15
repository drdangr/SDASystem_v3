"""
Сервис канонизации и дедупликации акторов.
Обрабатывает извлеченные акторы перед добавлением в граф:
- Лемматизация русских склонений (Украиной -> Украина)
- Канонизация через Wikidata API
- Извлечение метаданных и алиасов
"""
from typing import List, Dict, Optional
import logging
import os
import re

from backend.services.ner_spacy_service import detect_language, get_model_for_language, check_model_available

logger = logging.getLogger(__name__)

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not installed. Lemmatization will be disabled.")


class ActorCanonicalizationService:
    """
    Сервис для канонизации имен акторов.
    Поддерживает лемматизацию русского языка и интеграцию с Wikidata.
    """
    
    def __init__(
        self,
        use_wikidata: bool = True,
        use_lemmatization: bool = True,
        prefer_large_models: bool = False
    ):
        """
        Инициализация сервиса канонизации.
        
        Args:
            use_wikidata: Использовать Wikidata для канонизации
            use_lemmatization: Использовать лемматизацию для русского языка
            prefer_large_models: Предпочитать большие модели spaCy
        """
        self.use_wikidata = use_wikidata and os.getenv("WIKIDATA_ENABLED", "true").lower() == "true"
        self.use_lemmatization = use_lemmatization and SPACY_AVAILABLE
        self.prefer_large_models = prefer_large_models
        
        # Кэш загруженных моделей spaCy для лемматизации
        self._nlp_cache: Dict[str, any] = {}
        
        # Wikidata сервис будет инициализирован лениво
        self._wikidata_service = None
        
        logger.info(f"ActorCanonicalizationService initialized (wikidata={self.use_wikidata}, lemmatization={self.use_lemmatization})")
    
    def _get_nlp_model(self, language: str):
        """
        Получить загруженную модель spaCy для указанного языка.
        
        Args:
            language: Код языка ('ru' или 'en')
            
        Returns:
            Загруженная модель spaCy или None
        """
        if not self.use_lemmatization:
            return None
        
        if language in self._nlp_cache:
            return self._nlp_cache[language]
        
        model_name = get_model_for_language(language, prefer_large=self.prefer_large_models)
        
        if not check_model_available(model_name):
            logger.warning(f"Model {model_name} not available for lemmatization")
            return None
        
        try:
            nlp = spacy.load(model_name)
            self._nlp_cache[language] = nlp
            logger.debug(f"Loaded spaCy model for lemmatization: {model_name}")
            return nlp
        except Exception as e:
            logger.warning(f"Failed to load model {model_name}: {e}")
            return None
    
    def _lemmatize_russian(self, name: str) -> str:
        """
        Лемматизировать русское имя (привести к именительному падежу).
        Включает эвристики для исправления ошибок spaCy на одиночных фамилиях.
        
        Args:
            name: Имя в любом падеже (например, "Украиной", "Россией")
            
        Returns:
            Имя в именительном падеже (например, "Украина", "Россия")
        """
        if not self.use_lemmatization:
            return name
        
        nlp = self._get_nlp_model('ru')
        if not nlp:
            return name
        
        try:
            doc = nlp(name)
            # Для многословных имен (например, "Владимир Путин") лемматизируем каждое слово
            lemmatized_parts = []
            for token in doc:
                # Пропускаем знаки препинания
                if not token.is_punct:
                    lemmatized_parts.append(token.lemma_)
            
            lemmatized = " ".join(lemmatized_parts).strip()
            
            # --- HEURISTIC FIXES ---
            # Если лемматизация не изменила имя (или изменила только регистр),
            # а слово похоже на фамилию в косвенном падеже, применяем правила.
            
            original_lower = name.lower().strip()
            lemma_lower = lemmatized.lower().strip() if lemmatized else original_lower
            
            # Правила исправления окончаний для русских фамилий
            # Применяем только если это одно слово (или последнее слово во фразе)
            if lemma_lower == original_lower:
                words = lemma_lower.split()
                if not words:
                    return name
                
                last_word = words[-1]
                fixed_word = last_word
                
                # Правило 1: -ого/-его (Зеленского -> Зеленский)
                if last_word.endswith("ого") or last_word.endswith("его"):
                    fixed_word = last_word[:-3] + "ий"
                # Правило 2: -ова (Трампова -> Трампов - редко для муж, но бывает) 
                # Рискованно для женщин, но Wikidata должна исправить
                elif last_word.endswith("ова") and len(last_word) > 4: 
                     # Пропускаем "Слова", "Корова" и т.д. эвристически длиной
                     pass 
                # Правило 3: -ина (Путина -> Путин, Байдена -> Байден - тут сложнее)
                elif last_word.endswith("ина"):
                    # Путина -> Путин
                    fixed_word = last_word[:-1]
                # Правило 4: -ена (Байдена -> Байден)
                elif last_word.endswith("ена"):
                    fixed_word = last_word[:-1]
                # Правило 5: -ой (Украиной -> Украина) - spaCy обычно справляется, но на всякий случай
                elif last_word.endswith("ой") and "украин" in last_word:
                    fixed_word = last_word[:-2] + "а"

                if fixed_word != last_word:
                    words[-1] = fixed_word
                    lemmatized = " ".join(words)
                    logger.debug(f"Heuristic lemmatization applied: {name} -> {lemmatized}")

            # -----------------------

            # Если лемматизация не изменила имя, возвращаем оригинал
            if not lemmatized:
                return name
            
            logger.debug(f"Lemmatized '{name}' -> '{lemmatized}'")
            return lemmatized
        except Exception as e:
            logger.warning(f"Failed to lemmatize '{name}': {e}")
            return name
    
    def _normalize_russian_name(self, name: str) -> str:
        """
        Нормализовать русское имя: лемматизация + нормализация регистра.
        
        Args:
            name: Имя для нормализации
            
        Returns:
            Нормализованное имя
        """
        lemmatized = self._lemmatize_russian(name)
        
        # Нормализация регистра: первая буква заглавная, остальные строчные
        # Но сохраняем структуру для многословных имен
        parts = lemmatized.split()
        normalized_parts = []
        for part in parts:
            if part:
                # Первая буква заглавная, остальные строчные
                normalized_parts.append(part[0].upper() + part[1:].lower() if len(part) > 1 else part.upper())
        
        return " ".join(normalized_parts) if normalized_parts else lemmatized
    
    def canonicalize_actor(
        self,
        actor_name: str,
        actor_type: str,
        language: Optional[str] = None
    ) -> Dict:
        """
        Канонизировать актора: привести к канонической форме, получить алиасы и метаданные.
        
        Args:
            actor_name: Имя актора (может быть в любом падеже для русского)
            actor_type: Тип актора (person, country, organization и т.д.)
            language: Язык имени ('ru' или 'en'). Если None - определяется автоматически
            
        Returns:
            Словарь с полями:
            - canonical_name: каноническое имя
            - aliases: список алиасов [{"name": str, "type": str, "language": str}]
            - wikidata_qid: QID из Wikidata (если найден)
            - metadata: дополнительные метаданные (должности, страны и т.д.)
            - original_name: оригинальное имя (для сохранения как алиас)
        """
        if not actor_name or not actor_name.strip():
            return {
                "canonical_name": "",
                "aliases": [],
                "wikidata_qid": None,
                "metadata": {},
                "original_name": ""
            }
        
        original_name = actor_name.strip()
        
        # Определяем язык, если не указан
        if language is None:
            language = detect_language(original_name)

        def _is_latin_like(s: str) -> bool:
            # латиница/цифры/пробел/пунктуация, без кириллицы
            if not s:
                return False
            return not bool(re.search(r"[\u0400-\u04FF]", s))

        def _wikidata_search_with_fallback(name: str, primary_lang: str) -> Optional[Dict]:
            """
            Искать в Wikidata с fallback по языкам интерфейса/поиска.
            Важно: в нашем пайплайне имена часто уже в латинице (из LLM),
            поэтому для надежности всегда добавляем fallback на 'en'.
            """
            langs: List[str] = []
            if primary_lang:
                langs.append(primary_lang)
            # для uk -> ru (часто алиасы/описания в ru присутствуют лучше)
            if primary_lang == "uk":
                langs.append("ru")
            # если имя латиницей — 'en' чаще всего дает лучший hit
            if _is_latin_like(name):
                langs.append("en")
            else:
                # если имя кириллицей — пробуем ru/en тоже
                langs.extend(["ru", "en"])

            # уникализируем, сохраняя порядок
            seen = set()
            ordered_langs = []
            for l in langs:
                if l and l not in seen:
                    ordered_langs.append(l)
                    seen.add(l)

            for lang in ordered_langs:
                try:
                    res = self._wikidata_service.search_entity(
                        name=name,
                        language=lang,
                        expected_type=actor_type
                    )
                    if res:
                        return res
                except Exception:
                    continue
            return None
        
        # --- GARBAGE FILTERING ---
        # Отфильтровываем слишком длинные имена (вероятно, заголовки или ошибки экстракции)
        # Если это не организация с QID (которые мы еще не знаем, но если имя длинное и без контекста - подозрительно)
        if len(original_name) > 50 or len(original_name.split()) > 6:
            logger.warning(f"Skipping suspiciously long actor name: '{original_name}'")
            return {
                "canonical_name": original_name,
                "aliases": [],
                "wikidata_qid": None,
                "metadata": {},
                "original_name": original_name,
                "inferred_type": "organization" # Default to generic org if we must keep it
            }

        # --- KNOWN ENTITY OVERRIDES ---
        # Принудительное исправление типов для известных личностей, чтобы Wikidata искала правильно
        # Это временная мера, пока LLM не станет идеальной
        known_politicians_ru = ["Зеленский", "Путин", "Байден", "Трамп", "Макрон", "Шольц"]
        known_politicians_en = ["Zelensky", "Putin", "Biden", "Trump", "Macron", "Scholz"]
        
        check_name = original_name
        # Пытаемся нормализовать для проверки
        if language == 'ru' and self.use_lemmatization:
             check_name = self._normalize_russian_name(original_name)
        
        is_known_politician = False
        if any(p in check_name for p in known_politicians_ru) or any(p in check_name for p in known_politicians_en):
            is_known_politician = True
            actor_type = "politician" # Force type
            logger.debug(f"Forcing type 'politician' for known entity '{original_name}'")

        # Шаг 1: Лемматизация для русского языка (uk пока не лемматизируем)
        if language == 'ru' and self.use_lemmatization:
            lemmatized_name = self._normalize_russian_name(original_name)
        else:
            lemmatized_name = original_name
        
        # Шаг 2: Поиск в Wikidata (если включен)
        wikidata_qid = None
        wikidata_canonical = None
        wikidata_aliases = []
        wikidata_metadata = {}
        wikidata_type = None
        
        if self.use_wikidata:
            try:
                from backend.services.wikidata_service import WikidataService
                
                if self._wikidata_service is None:
                    self._wikidata_service = WikidataService()
                
                # Поиск по лемматизированному имени с fallback uk->ru->en
                search_result = _wikidata_search_with_fallback(lemmatized_name, language)
                
                if search_result:
                    wikidata_qid = search_result.get("qid")
                    wikidata_canonical = search_result.get("canonical_name")
                    wikidata_aliases = search_result.get("aliases", [])
                    wikidata_metadata = search_result.get("metadata", {})
                    wikidata_type = search_result.get("type")
                    
                    logger.debug(f"Found Wikidata entity for '{lemmatized_name}': QID={wikidata_qid}")
            except Exception as e:
                logger.warning(f"Wikidata search failed for '{lemmatized_name}': {e}")
        
        # Шаг 3: Определение канонического имени
        if wikidata_canonical:
            canonical_name = wikidata_canonical
        elif lemmatized_name != original_name:
            canonical_name = lemmatized_name
        else:
            canonical_name = original_name
        
        # Шаг 4: Формирование списка алиасов
        aliases = []
        
        # Добавляем оригинальное имя как алиас (если отличается от канонического)
        if original_name.lower() != canonical_name.lower():
            aliases.append({
                "name": original_name,
                "type": "original",
                "language": language
            })
        
        # Добавляем лемматизированное имя как алиас (если отличается)
        if lemmatized_name != canonical_name and lemmatized_name != original_name:
            aliases.append({
                "name": lemmatized_name,
                "type": "lemmatized",
                "language": language
            })
        
        # Добавляем алиасы из Wikidata
        for alias in wikidata_aliases:
            # Проверяем, что алиас не дублирует уже добавленные
            alias_name = alias.get("name", "")
            if alias_name and alias_name.lower() not in [a["name"].lower() for a in aliases]:
                aliases.append({
                    "name": alias_name,
                    "type": alias.get("type", "alias"),
                    "language": alias.get("language", language)
                })
        
        # Шаг 5: Формирование метаданных
        metadata = {}
        if wikidata_metadata:
            metadata.update(wikidata_metadata)
        
        # Добавляем информацию о языке оригинала
        metadata["original_language"] = language
        
        return {
            "canonical_name": canonical_name,
            "aliases": aliases,
            "wikidata_qid": wikidata_qid,
            "metadata": metadata,
            "original_name": original_name,
            "inferred_type": wikidata_type
        }
    
    def canonicalize_batch(self, actors: List[Dict], default_language: Optional[str] = None) -> List[Dict]:
        """
        Канонизировать список акторов пакетно.
        
        Args:
            actors: Список словарей с полями:
                - name: имя актора
                - type: тип актора
                - confidence: уверенность (опционально)
                - language: язык (опционально, определяется автоматически)
            default_language: Язык по умолчанию, если не указан для актора
        
        Returns:
            Список канонизированных акторов с дополнительными полями:
            - canonical_name, aliases, wikidata_qid, metadata
        """
        canonicalized = []
        
        for actor in actors:
            name = actor.get("name")
            if not name:
                continue
            
            actor_type = actor.get("type", "organization")
            # Язык для канонизации:
            # - если у актора есть original_name, определяем язык по нему (это устойчивее для LLM-канона)
            # - иначе берём language/default_language как раньше
            language = actor.get("language") or default_language
            original_name = actor.get("original_name")
            if original_name:
                language = detect_language(str(original_name))
            confidence = actor.get("confidence")
            
            # Канонизируем актора
            canonical = self.canonicalize_actor(name, actor_type, language)

            # Важно для дедупликации: если LLM дал original_name (как в тексте),
            # добавляем его как алиас, даже если canonicalize_actor() получал уже латинское имя.
            # (иначе теряем связь Zelenskyy <-> Зеленский/Зеленський)
            if original_name:
                try:
                    orig_str = str(original_name).strip()
                except Exception:
                    orig_str = ""
                if orig_str:
                    aliases = canonical.get("aliases") or []
                    # проверка на дубль
                    if not any((a.get("name", "").lower() == orig_str.lower()) for a in aliases if isinstance(a, dict)):
                        aliases.append({
                            "name": orig_str,
                            "type": "original_text",
                            "language": detect_language(orig_str)
                        })
                        canonical["aliases"] = aliases
            
            # Обновляем тип, если он был уточнен в Wikidata
            final_type = canonical.get("inferred_type") or actor_type
            
            # Объединяем с исходными данными
            result = {
                **actor,
                **canonical,
                "type": final_type,
                "confidence": confidence
            }
            
            if "inferred_type" in result:
                del result["inferred_type"]
            
            canonicalized.append(result)
        
        return canonicalized

