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
        
        # Шаг 1: Лемматизация для русского языка
        if language == 'ru' and self.use_lemmatization:
            lemmatized_name = self._normalize_russian_name(original_name)
        else:
            lemmatized_name = original_name
        
        # Шаг 2: Поиск в Wikidata (если включен)
        wikidata_qid = None
        wikidata_canonical = None
        wikidata_aliases = []
        wikidata_metadata = {}
        
        if self.use_wikidata:
            try:
                from backend.services.wikidata_service import WikidataService
                
                if self._wikidata_service is None:
                    self._wikidata_service = WikidataService()
                
                # Поиск по лемматизированному имени
                search_result = self._wikidata_service.search_entity(lemmatized_name, language)
                
                if search_result:
                    wikidata_qid = search_result.get("qid")
                    wikidata_canonical = search_result.get("canonical_name")
                    wikidata_aliases = search_result.get("aliases", [])
                    wikidata_metadata = search_result.get("metadata", {})
                    
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
            "original_name": original_name
        }
    
    def canonicalize_batch(self, actors: List[Dict]) -> List[Dict]:
        """
        Канонизировать список акторов пакетно.
        
        Args:
            actors: Список словарей с полями:
                - name: имя актора
                - type: тип актора
                - confidence: уверенность (опционально)
                - language: язык (опционально, определяется автоматически)
        
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
            language = actor.get("language")
            confidence = actor.get("confidence")
            
            # Канонизируем актора
            canonical = self.canonicalize_actor(name, actor_type, language)
            
            # Объединяем с исходными данными
            result = {
                **actor,
                **canonical,
                "confidence": confidence
            }
            
            canonicalized.append(result)
        
        return canonicalized

