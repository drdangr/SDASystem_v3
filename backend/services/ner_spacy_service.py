"""
Улучшенный NER сервис с интеграцией spaCy для более точного извлечения акторов.

Использование:
    service = NERSpacyService()
    service.load_gazetteer(actors_list)
    known_ids, new_actors = service.extract_actors_from_text(text)
"""
from typing import List, Dict, Tuple, Optional
import logging
import re

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logging.warning("spaCy not installed. Install with: pip install spacy && python -m spacy download ru_core_news_lg")

from backend.models.entities import Actor, ActorType


logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """
    Определить язык текста.

    Простая эвристика:
    - 'uk' если встречаются украинские буквы (і/ї/є/ґ)
    - 'ru' если встречается кириллица, но нет украинских букв
    - иначе 'en'
    
    Args:
        text: Текст для анализа
        
    Returns:
        'ru' если обнаружена кириллица, иначе 'en'
    """
    if not text:
        return 'en'
    
    # Украинские специфические буквы (в русском их нет)
    ukrainian_pattern = re.compile(r'[ІіЇїЄєҐґ]')
    if ukrainian_pattern.search(text):
        return 'uk'

    # Проверяем наличие кириллических символов (RU/UA/etc.)
    cyrillic_pattern = re.compile(r'[А-Яа-яЁёІіЇїЄєҐґ]')
    has_cyrillic = bool(cyrillic_pattern.search(text))
    
    # Подсчитываем процент кириллицы
    cyrillic_chars = len(cyrillic_pattern.findall(text))
    total_chars = len(re.findall(r'[А-Яа-яЁёA-Za-z]', text))
    
    if total_chars == 0:
        return 'en'
    
    cyrillic_ratio = cyrillic_chars / total_chars
    
    # Если больше 30% кириллицы - считаем русским (если не uk — см. выше)
    if cyrillic_ratio > 0.3 or has_cyrillic:
        return 'ru'
    
    return 'en'


def get_model_for_language(language: str, prefer_large: bool = False) -> str:
    """
    Получить название spaCy модели для указанного языка.
    
    Args:
        language: Код языка ('ru' или 'en')
        prefer_large: Предпочитать большие модели (lg) вместо средних (md)
        
    Returns:
        Название модели spaCy
    """
    if language == 'ru':
        if prefer_large:
            return 'ru_core_news_lg'
        else:
            return 'ru_core_news_md'  # Средняя модель - хороший баланс
    elif language == 'uk':
        # У spaCy нет стандартной официальной uk-модели в базовой поставке.
        # Для best-effort используем многоязычную NER-модель.
        return 'xx_ent_wiki_sm'
    else:
        if prefer_large:
            return 'en_core_web_lg'
        else:
            return 'en_core_web_sm'  # Малая модель - быстрая и доступная


def check_model_available(model_name: str) -> bool:
    """
    Проверить, доступна ли модель spaCy.
    
    Args:
        model_name: Название модели
        
    Returns:
        True если модель доступна, False иначе
    """
    if not SPACY_AVAILABLE:
        return False
    
    try:
        import spacy.util
        # Попытка найти модель
        spacy.load(model_name)
        return True
    except (OSError, IOError):
        return False


class NERSpacyService:
    """
    NER сервис на основе spaCy для извлечения именованных сущностей.
    Поддерживает канонизацию через gazetteer.
    """

    def __init__(self, model_name: str = "ru_core_news_lg", use_multilang: bool = True):
        """
        Инициализация spaCy модели.

        Args:
            model_name: Название spaCy модели. Для русского: "ru_core_news_lg"
                       Для английского: "en_core_web_lg"
                       Для многоязычной: "xx_ent_wiki_sm"
            use_multilang: Использовать многоязычную модель если доступна
        """
        self.gazetteer: Dict[str, Actor] = {}
        self.canonical_map: Dict[str, str] = {}  # alias -> actor_id
        
        self.nlp = None
        self.model_name = model_name
        
        if not SPACY_AVAILABLE:
            logger.warning("spaCy не установлен. Используйте базовый NERService.")
            return
        
        try:
            # Попытка загрузить модель
            self.nlp = spacy.load(model_name)
            logger.info(f"Загружена spaCy модель: {model_name}")
        except OSError:
            # Попытка загрузить многоязычную модель
            if use_multilang:
                try:
                    self.nlp = spacy.load("xx_ent_wiki_sm")
                    logger.info("Загружена многоязычная spaCy модель: xx_ent_wiki_sm")
                except OSError:
                    logger.error(
                        f"Не удалось загрузить spaCy модель {model_name}. "
                        "Установите модель: python -m spacy download {model_name}"
                    )
            else:
                logger.error(f"Не удалось загрузить spaCy модель {model_name}")

        # Маппинг типов spaCy на наши типы
        self.type_mapping = {
            "PERSON": ActorType.PERSON,
            "ORG": ActorType.ORGANIZATION,
            "GPE": ActorType.COUNTRY,  # Geopolitical entity
            "LOC": ActorType.COUNTRY,   # Location
            "MISC": ActorType.ORGANIZATION,
        }

    def load_gazetteer(self, actors: List[Actor]) -> None:
        """Загрузить известных акторов в gazetteer для канонизации"""
        self.gazetteer = {}
        self.canonical_map = {}
        
        for actor in actors:
            self.gazetteer[actor.id] = actor
            
            # Добавить каноническое имя
            canonical_lower = actor.canonical_name.lower().strip()
            self.canonical_map[canonical_lower] = actor.id
            
            # Добавить все алиасы
            for alias_entry in actor.aliases:
                alias = alias_entry.get("name", "").lower().strip()
                if alias:
                    self.canonical_map[alias] = actor.id
        
        logger.info(f"Загружено {len(actors)} акторов в gazetteer")

    def extract_actors_from_text(
        self,
        text: str,
        context: Optional[Dict] = None,
        confidence_threshold: float = 0.7
    ) -> Tuple[List[str], List[Actor]]:
        """
        Извлечь акторов из текста с помощью spaCy NER.

        Args:
            text: Текст для анализа
            context: Дополнительный контекст (не используется пока)
            confidence_threshold: Минимальная уверенность для включения

        Returns:
            Tuple[List[str], List[Actor]]:
                - Список ID известных акторов
                - Список новых обнаруженных акторов
        """
        if not self.nlp:
            logger.warning("spaCy модель не загружена. Используйте базовый NERService.")
            return [], []

        known_actors = []
        new_actors = []
        seen_texts = set()  # Для дедупликации

        # Обработка текста через spaCy
        doc = self.nlp(text)

        # Извлечение именованных сущностей
        for ent in doc.ents:
            # Пропустить если слишком короткое или уже видели
            ent_text = ent.text.strip()
            ent_text_lower = ent_text.lower()
            
            if len(ent_text) < 2 or ent_text_lower in seen_texts:
                continue
            
            seen_texts.add(ent_text_lower)

            # Определить тип
            actor_type = self._map_spacy_type(ent.label_)
            
            # Попытка найти в gazetteer (канонизация)
            matched_actor_id = self._find_in_gazetteer(ent_text)
            
            if matched_actor_id:
                # Найден известный актор
                if matched_actor_id not in known_actors:
                    known_actors.append(matched_actor_id)
            else:
                # Новый актор - создать
                # Вычислить confidence на основе эвристик (spaCy не предоставляет scores напрямую)
                confidence = self._calculate_confidence(ent, text)
                
                if confidence >= confidence_threshold:
                    new_actor = Actor(
                        id=f"actor_{hash(ent_text_lower) % 10**12}",  # Детерминированный ID
                        canonical_name=ent_text,
                        actor_type=actor_type,
                        aliases=[],
                        metadata={
                            "confidence": confidence,
                            "auto_extracted": True,
                            "source": "spacy",
                            "spacy_label": ent.label_
                        }
                    )
                    new_actors.append(new_actor)

        logger.debug(f"Извлечено: {len(known_actors)} известных, {len(new_actors)} новых акторов")
        return known_actors, new_actors

    def _map_spacy_type(self, spacy_label: str) -> ActorType:
        """Маппинг типов spaCy на наши типы акторов"""
        return self.type_mapping.get(spacy_label, ActorType.ORGANIZATION)
    
    def _calculate_confidence(self, ent, text: str) -> float:
        """
        Вычислить confidence для сущности на основе эвристик.
        
        spaCy не предоставляет confidence scores напрямую, поэтому используем:
        - Тип сущности (ORG, PERSON обычно более надежны)
        - Длина сущности (более длинные обычно более надежны)
        - Контекст (наличие заглавных букв, позиция в тексте)
        - Повторяемость в тексте
        
        Returns:
            Confidence score от 0.0 до 1.0
        """
        confidence = 0.7  # Базовая уверенность
        
        # Тип сущности влияет на уверенность
        label = ent.label_
        if label in ["PERSON", "ORG"]:
            confidence += 0.1  # Персоны и организации обычно более надежны
        elif label in ["GPE", "LOC"]:
            confidence += 0.05  # Географические объекты тоже надежны
        
        # Длина сущности (более длинные обычно более надежны)
        ent_length = len(ent.text)
        if ent_length >= 5:
            confidence += 0.05
        if ent_length >= 10:
            confidence += 0.05
        
        # Проверка на заглавные буквы (обычно признак именованной сущности)
        if ent.text[0].isupper():
            confidence += 0.05
        
        # Проверка повторяемости в тексте (если упоминается несколько раз - выше уверенность)
        text_lower = text.lower()
        ent_lower = ent.text.lower()
        mentions = text_lower.count(ent_lower)
        if mentions > 1:
            confidence += min(0.1, (mentions - 1) * 0.03)
        
        # Ограничиваем до 0.0-1.0
        confidence = max(0.5, min(0.95, confidence))
        
        return confidence

    def _find_in_gazetteer(self, entity_text: str) -> Optional[str]:
        """
        Найти актора в gazetteer по тексту сущности.
        Использует точное и частичное сопоставление с проверкой на разумность совпадения.
        """
        entity_lower = entity_text.lower().strip()
        
        if not entity_lower or len(entity_lower) < 2:
            return None
        
        # 1. Точное совпадение (высший приоритет)
        if entity_lower in self.canonical_map:
            return self.canonical_map[entity_lower]
        
        # 2. Поиск по известным акторам с проверкой разумности
        best_match = None
        best_score = 0.0
        
        for actor_id, actor in self.gazetteer.items():
            canonical_lower = actor.canonical_name.lower()
            
            # Точное совпадение канонического имени
            if entity_lower == canonical_lower:
                return actor_id
            
            # Проверка алиасов (точное совпадение)
            for alias_entry in actor.aliases:
                alias = alias_entry.get("name", "").lower().strip()
                if entity_lower == alias:
                    return actor_id
            
            # Частичное совпадение (только если разумно)
            # Проверяем что одна строка содержит другую как целое слово
            entity_words = set(entity_lower.split())
            canonical_words = set(canonical_lower.split())
            alias_words_sets = [set(alias_entry.get("name", "").lower().split()) 
                               for alias_entry in actor.aliases]
            
            # Если все слова сущности есть в каноническом имени или алиасе
            if entity_words and len(entity_words) > 0:
                # Проверка канонического имени
                if entity_words.issubset(canonical_words) or canonical_words.issubset(entity_words):
                    # Дополнительная проверка: совпадение должно быть значимым
                    overlap = len(entity_words & canonical_words)
                    total = len(entity_words | canonical_words)
                    score = overlap / total if total > 0 else 0
                    if score >= 0.6 and len(entity_words) >= 2:  # Минимум 60% совпадения и хотя бы 2 слова
                        if score > best_score:
                            best_score = score
                            best_match = actor_id
                
                # Проверка алиасов
                for alias_words in alias_words_sets:
                    if alias_words and (entity_words.issubset(alias_words) or alias_words.issubset(entity_words)):
                        overlap = len(entity_words & alias_words)
                        total = len(entity_words | alias_words)
                        score = overlap / total if total > 0 else 0
                        if score >= 0.6:
                            if score > best_score:
                                best_score = score
                                best_match = actor_id
        
        # Возвращаем лучшее совпадение только если оно достаточно хорошее
        if best_score >= 0.6:
            return best_match
        
        return None

    def canonicalize_actor(self, actor_name: str) -> Optional[str]:
        """Найти канонический ID актора по имени"""
        return self._find_in_gazetteer(actor_name)

    def extract_with_canonical_names(
        self,
        text: str,
        prefer_canonical: bool = True
    ) -> List[Dict]:
        """
        Извлечь акторов с каноническими именами.
        
        Returns:
            Список словарей: [
                {
                    "name": "canonical_name",
                    "type": "person|company|...",
                    "confidence": 0.0-1.0,
                    "original_text": "текст из статьи",
                    "actor_id": "actor_xxx" (если найден в gazetteer)
                }
            ]
        """
        if not self.nlp:
            return []

        known_ids, new_actors = self.extract_actors_from_text(text)
        result = []

        # Добавить известных акторов
        for actor_id in known_ids:
            actor = self.gazetteer.get(actor_id)
            if actor:
                # Поддержка как Enum так и строки
                actor_type_value = actor.actor_type.value if hasattr(actor.actor_type, 'value') else str(actor.actor_type)
                result.append({
                    "name": actor.canonical_name,
                    "type": actor_type_value,
                    "confidence": 0.9,  # Высокая уверенность для известных
                    "original_text": actor.canonical_name,
                    "actor_id": actor_id
                })

        # Добавить новых акторов
        for actor in new_actors:
            # Поддержка как Enum так и строки
            actor_type_value = actor.actor_type.value if hasattr(actor.actor_type, 'value') else str(actor.actor_type)
            result.append({
                "name": actor.canonical_name,
                "type": actor_type_value,
                "confidence": actor.metadata.get("confidence", 0.7),
                "original_text": actor.canonical_name,
                "actor_id": actor.id
            })

        return result


def create_hybrid_ner_service(
    llm_service,
    use_spacy: bool = True,
    spacy_model: Optional[str] = None,
    auto_detect_language: bool = True,
    prefer_large_models: bool = False
) -> "HybridNERService":
    """
    Создать гибридный NER сервис, объединяющий spaCy и LLM.
    По умолчанию автоматически определяет язык текста и выбирает соответствующую модель.

    Args:
        llm_service: Экземпляр LLMService
        use_spacy: Использовать spaCy для первичного извлечения
        spacy_model: Название spaCy модели (если None - будет автоматически выбираться по языку)
        auto_detect_language: Автоматически определять язык и выбирать модель
        prefer_large_models: Предпочитать большие модели (lg) вместо средних/малых

    Returns:
        HybridNERService
    """
    return HybridNERService(
        llm_service, 
        use_spacy=use_spacy, 
        spacy_model=spacy_model,
        auto_detect_language=auto_detect_language,
        prefer_large_models=prefer_large_models
    )


class HybridNERService:
    """
    Гибридный NER сервис: spaCy для быстрого извлечения + LLM для канонизации.
    Автоматически определяет язык текста и выбирает соответствующую модель spaCy.
    """
    
    def __init__(
        self,
        llm_service,
        use_spacy: bool = True,
        spacy_model: Optional[str] = None,  # Если None - будет автоматически выбираться по языку
        auto_detect_language: bool = True,  # Автоматически определять язык и выбирать модель
        prefer_large_models: bool = False  # Предпочитать большие модели (lg)
    ):
        self.llm_service = llm_service
        self.use_spacy = use_spacy and SPACY_AVAILABLE
        self.auto_detect_language = auto_detect_language
        self.prefer_large_models = prefer_large_models
        self.default_model = spacy_model or "en_core_web_sm"
        
        # Кэш загруженных моделей для быстрого переключения
        self._model_cache: Dict[str, NERSpacyService] = {}
        
        if self.use_spacy:
            # Предзагружаем модель по умолчанию
            self._load_model(self.default_model)
        else:
            self.spacy_service = None
        
        logger.info(f"Создан HybridNERService (spaCy: {self.use_spacy}, auto-detect: {auto_detect_language})")
    
    def _load_model(self, model_name: str) -> Optional[NERSpacyService]:
        """
        Загрузить модель spaCy с кэшированием.
        
        Args:
            model_name: Название модели
            
        Returns:
            NERSpacyService или None если модель недоступна
        """
        if model_name in self._model_cache:
            return self._model_cache[model_name]
        
        try:
            service = NERSpacyService(model_name=model_name)
            if service.nlp:  # Проверяем, что модель успешно загружена
                self._model_cache[model_name] = service
                logger.debug(f"Загружена модель spaCy: {model_name}")
                return service
            else:
                logger.warning(f"Модель {model_name} не загружена")
                return None
        except Exception as e:
            logger.warning(f"Не удалось загрузить модель {model_name}: {e}")
            return None
    
    def _get_model_for_text(self, text: str) -> Optional[NERSpacyService]:
        """
        Получить подходящую модель spaCy для текста.
        
        Args:
            text: Текст для анализа
            
        Returns:
            NERSpacyService или None
        """
        if not self.use_spacy:
            return None
        
        if self.auto_detect_language:
            # Определяем язык текста
            language = detect_language(text)
            model_name = get_model_for_language(language, prefer_large=self.prefer_large_models)
            
            # Пробуем загрузить модель для этого языка
            service = self._load_model(model_name)
            if service:
                return service
            
            # Если модель недоступна, пробуем альтернативу
            if language == 'ru':
                # Пробуем другие русские модели
                for alt_model in ['ru_core_news_sm', 'ru_core_news_lg', 'ru_core_news_md']:
                    if alt_model != model_name:
                        service = self._load_model(alt_model)
                        if service:
                            logger.info(f"Используется альтернативная модель: {alt_model}")
                            return service
            else:
                # Пробуем другие английские модели
                for alt_model in ['en_core_web_sm', 'en_core_web_lg']:
                    if alt_model != model_name:
                        service = self._load_model(alt_model)
                        if service:
                            logger.info(f"Используется альтернативная модель: {alt_model}")
                            return service
        
        # Возвращаем модель по умолчанию
        if self.default_model in self._model_cache:
            return self._model_cache[self.default_model]
        
        return self._load_model(self.default_model)

    def load_gazetteer(self, actors: List[Actor]) -> None:
        """Загрузить gazetteer во все загруженные модели"""
        for service in self._model_cache.values():
            if service:
                service.load_gazetteer(actors)

    def extract_actors(
        self,
        text: str,
        use_llm: bool = True,
        llm_for_canonical_only: bool = False,
        low_confidence_threshold: float = 0.75,
        use_llm_for_low_confidence: bool = True
    ) -> List[Dict]:
        """
        Извлечь акторов гибридным методом с умной проверкой через LLM.

        Стратегия:
        1. spaCy извлекает сущности быстро (первичный метод)
        2. Если confidence < low_confidence_threshold - перепроверяем через LLM
        3. Если spaCy пропустил сущности (мало результатов) - используем LLM для дополнения
        4. LLM также используется для канонизации найденных сущностей

        Args:
            text: Текст для анализа
            use_llm: Использовать LLM для улучшения результатов
            llm_for_canonical_only: Использовать LLM только для канонизации существующих
            low_confidence_threshold: Порог уверенности для перепроверки через LLM
            use_llm_for_low_confidence: Перепроверять сущности с низким confidence через LLM

        Returns:
            Список акторов в формате: [{"name": str, "type": str, "confidence": float}]
        """
        result = []
        spacy_used = False
        low_confidence_entities = []
        
        # Этап 1: Быстрое извлечение через spaCy (если доступно и модель загружена)
        # Автоматически выбираем модель на основе языка текста
        spacy_service = self._get_model_for_text(text)
        if self.use_spacy and spacy_service and spacy_service.nlp:
            try:
                spacy_results = spacy_service.extract_with_canonical_names(text)
                if spacy_results:
                    # Разделяем на высокую и низкую уверенность
                    for actor in spacy_results:
                        confidence = actor.get('confidence', 0.7)
                        if confidence >= low_confidence_threshold:
                            # Высокая уверенность - используем как есть
                            result.append(actor)
                        else:
                            # Низкая уверенность - помечаем для перепроверки
                            low_confidence_entities.append(actor)
                    
                    spacy_used = True
                    logger.debug(f"spaCy извлек {len(spacy_results)} акторов "
                               f"({len(result)} высокий confidence, "
                               f"{len(low_confidence_entities)} низкий confidence)")
            except Exception as e:
                logger.warning(f"Ошибка при использовании spaCy: {e}, fallback на LLM")
        
        # Этап 2: Использование LLM для перепроверки и дополнения
        if use_llm:
            try:
                # Проверяем, нужно ли вызывать LLM
                need_llm = False
                llm_reason = []
                
                # Причина 1: Есть сущности с низким confidence для перепроверки
                if use_llm_for_low_confidence and low_confidence_entities:
                    need_llm = True
                    llm_reason.append(f"{len(low_confidence_entities)} низкий confidence")
                
                # Причина 2: spaCy не нашел достаточно акторов (возможно что-то пропустил)
                if spacy_used and len(result) < 3:
                    need_llm = True
                    llm_reason.append("мало результатов от spaCy")
                
                # Причина 3: spaCy вообще не сработал
                if not spacy_used:
                    need_llm = True
                    llm_reason.append("spaCy недоступен")
                
                if need_llm:
                    logger.debug(f"Использование LLM: {', '.join(llm_reason)}")
                    
                    # Полное извлечение через LLM
                    llm_results = self.llm_service.extract_actors(text)
                    
                    if spacy_used:
                        # Объединяем результаты
                        result_names = {r['name'].lower() for r in result}
                        
                        # Сначала перепроверяем сущности с низким confidence
                        if use_llm_for_low_confidence and low_confidence_entities:
                            for low_conf_actor in low_confidence_entities:
                                low_conf_name = low_conf_actor['name'].lower()
                                # Ищем в LLM результатах - есть ли подтверждение?
                                found_in_llm = any(
                                    llm_name.lower() == low_conf_name or 
                                    low_conf_name in llm_name.lower() or 
                                    llm_name.lower() in low_conf_name
                                    for llm_name in [a['name'] for a in llm_results]
                                )
                                
                                if found_in_llm:
                                    # LLM подтвердил - повышаем confidence
                                    low_conf_actor['confidence'] = min(0.9, low_conf_actor['confidence'] + 0.15)
                                    result.append(low_conf_actor)
                                    result_names.add(low_conf_name)
                                    logger.debug(f"LLM подтвердил: {low_conf_actor['name']} "
                                               f"(confidence: {low_conf_actor['confidence']:.2f})")
                        
                        # Добавляем новые сущности из LLM, которых нет в spaCy
                        new_from_llm = 0
                        for llm_actor in llm_results:
                            llm_name_lower = llm_actor['name'].lower()
                            if llm_name_lower not in result_names:
                                # Проверяем, не было ли это в low_confidence_entities
                                was_low_conf = any(
                                    e['name'].lower() == llm_name_lower 
                                    for e in low_confidence_entities
                                )
                                if not was_low_conf:
                                    result.append(llm_actor)
                                    result_names.add(llm_name_lower)
                                    new_from_llm += 1
                        
                        logger.debug(f"LLM добавил {new_from_llm} новых акторов, "
                                   f"подтвердил {len([a for a in result if a.get('confidence', 0) > low_confidence_threshold + 0.1])} низкоконфиденциальных")
                    else:
                        # Fallback: использовать только LLM результаты
                        result = llm_results
                        logger.debug("Использован только LLM (spaCy недоступен)")
                
            except Exception as e:
                logger.error(f"Ошибка при использовании LLM: {e}")
                # Если была ошибка LLM, но есть результаты от spaCy - используем их
                if not result and spacy_used:
                    # Возвращаем даже низкоконфиденциальные, лучше что-то чем ничего
                    result.extend(spacy_results)
                    logger.debug("Ошибка LLM, используем все результаты spaCy (включая низкий confidence)")
        
        return result

