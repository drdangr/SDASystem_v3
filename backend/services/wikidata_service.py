"""
Сервис для работы с Wikidata API.
Используется для канонизации имен акторов и получения метаданных.
"""
import requests
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from backend.models.entities import ActorType

logger = logging.getLogger(__name__)


class WikidataService:
    """
    Сервис для поиска и получения информации о сущностях из Wikidata.
    """
    
    WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
    WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
    
    # Mapping of QIDs to ActorTypes
    TYPE_MAPPINGS = {
        # Politician / Government Official
        "Q82955": ActorType.POLITICIAN, # politician
        "Q30461": ActorType.POLITICIAN, # president
        "Q193391": ActorType.POLITICIAN, # diplomat
        "Q2823591": ActorType.POLITICIAN, # minister
        "Q14212": ActorType.POLITICIAN, # prime minister
        "Q40348": ActorType.POLITICIAN, # lawyer (often politicians are lawyers)
        "Q66715801": ActorType.POLITICIAN, # politician of ...
        
        # Business Person
        "Q43845": ActorType.PERSON, # businessperson
        "Q131524": ActorType.PERSON, # entrepreneur
        
        # Person (General)
        "Q5": ActorType.PERSON, # human

        # Company
        "Q4830453": ActorType.COMPANY, # business enterprise
        "Q783794": ActorType.COMPANY, # company
        "Q891723": ActorType.COMPANY, # public company
        "Q167037": ActorType.COMPANY, # corporation
        "Q6881511": ActorType.COMPANY, # enterprise
        "Q43229": ActorType.ORGANIZATION, # organization (general)

        # Government
        "Q327333": ActorType.GOVERNMENT, # government agency
        "Q192350": ActorType.GOVERNMENT, # ministry
        "Q7188": ActorType.GOVERNMENT, # government
        "Q2215624": ActorType.GOVERNMENT, # executive branch
        "Q35525": ActorType.GOVERNMENT, # White House (specific)
        "Q27468": ActorType.GOVERNMENT, # The Kremlin (specific)

        # International Org
        "Q48836": ActorType.INT_ORG, # international organization
        "Q7131": ActorType.INT_ORG, # intergovernmental organization
        "Q126261": ActorType.INT_ORG, # supranational organization

        # Organization (General)
        "Q79913": ActorType.ORGANIZATION, # non-governmental organization
        "Q7278": ActorType.ORGANIZATION, # political party
        "Q16334295": ActorType.ORGANIZATION, # group of people
        
        # Country
        "Q6256": ActorType.COUNTRY, # country
        "Q3624078": ActorType.COUNTRY, # sovereign state
        "Q3024240": ActorType.COUNTRY, # historical country (USSR)
    }

    def __init__(self, cache_ttl: int = 86400):
        """
        Инициализация сервиса Wikidata.
        
        Args:
            cache_ttl: Время жизни кэша в секундах (по умолчанию 24 часа)
        """
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Dict] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        
        logger.info(f"WikidataService initialized (cache_ttl={cache_ttl}s)")
    
    def _is_cache_valid(self, key: str) -> bool:
        """Проверить, валиден ли кэш для ключа"""
        if key not in self._cache:
            return False
        
        timestamp = self._cache_timestamps.get(key)
        if not timestamp:
            return False
        
        age = datetime.utcnow() - timestamp
        return age.total_seconds() < self.cache_ttl
    
    def _get_cached(self, key: str) -> Optional[Dict]:
        """Получить значение из кэша"""
        if self._is_cache_valid(key):
            return self._cache[key]
        return None
    
    def _set_cached(self, key: str, value: Dict):
        """Сохранить значение в кэш"""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.utcnow()
    
    def search_entity(
        self,
        name: str,
        language: str = "ru",
        limit: int = 5,
        expected_type: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Поиск сущности в Wikidata по имени.
        
        Args:
            name: Имя для поиска
            language: Язык поиска ('ru' или 'en')
            limit: Максимальное количество результатов
            expected_type: Ожидаемый тип актора (person, country, etc.) для фильтрации
            
        Returns:
            Словарь с полями:
            - qid: QID сущности (например, "Q7747")
            - canonical_name: каноническое имя
            - aliases: список алиасов
            - metadata: метаданные (должности, страны и т.д.)
            Или None если не найдено
        """
        if not name or not name.strip():
            return None
        
        # Проверяем кэш (добавляем expected_type в ключ, так как результат может зависеть от фильтра)
        cache_key = f"search:{language}:{name.lower()}:{expected_type or 'any'}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.debug(f"Cache hit for '{name}' (type={expected_type})")
            return cached
        
        try:
            # Поиск через Wikidata Search API
            params = {
                "action": "wbsearchentities",
                "search": name,
                "language": language,
                "format": "json",
                "limit": limit
            }
            
            headers = {
                'User-Agent': 'SDAS Actor Canonicalization Service/1.0 (https://github.com/your-repo)'
            }
            response = requests.get(self.WIKIDATA_API_URL, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            search_results = data.get("search", [])
            
            if not search_results:
                logger.debug(f"No Wikidata results for '{name}'")
                self._set_cached(cache_key, None)
                return None
            
            # --- STRICT TYPE CHECKING & SELECTION LOGIC ---
            
            # Если указан ожидаемый тип, сначала ищем точное совпадение по типу
            best_match = None
            
            if expected_type:
                # Нормализуем ожидаемый тип
                t_lower = expected_type.lower()
                
                # Запрашиваем детали для топ-3 результатов, чтобы проверить их instance_of
                top_results = search_results[:3]
                for res in top_results:
                    qid = res.get("id")
                    info = self.get_entity_info(qid, language)
                    if not info:
                        continue
                        
                    instances = info.get("metadata", {}).get("instance_of_qids", [])
                    
                    # Логика проверки типов
                    is_match = False
                    
                    if t_lower in ["person", "politician"]:
                        # Q5 = Human
                        if "Q5" in instances:
                            is_match = True
                    elif t_lower in ["country"]:
                        # Q6256=Country, Q3624078=Sovereign State, Q3024240=Historical Country
                        if any(x in instances for x in ["Q6256", "Q3624078", "Q3024240"]):
                            is_match = True
                    elif t_lower in ["organization", "company", "government", "int_org"]:
                         # Q43229=Org, Q4830453=Business, etc.
                         # Для организаций проверка сложнее, так как типов много.
                         # Упрощенно: если это НЕ человек и НЕ географический объект (если не страна)
                         if "Q5" not in instances:
                             is_match = True

                    if is_match:
                        # Дополнительная проверка: если ищем человека, а это "фамилия" (даже если instance of human - вряд ли, но вдруг)
                        desc = res.get("description", "").lower()
                        if "family name" in desc or "фамилия" in desc:
                             # Но если это ТОЧНО Human (Q5), то это не фамилия. 
                             # Фамилии обычно Q101352.
                             if "Q101352" in instances:
                                 is_match = False
                        
                        if is_match:
                            best_match = info
                            break
            
            # Если строгая проверка не дала результата или тип не был указан, используем эвристику
            if not best_match:
                # Перебираем результаты, чтобы найти наиболее подходящий (как раньше)
                selected_res_item = None
                
                # 1. Проход: ищем известных людей (если не ищем явно организацию)
                if expected_type not in ["organization", "company", "country"]:
                    for res in search_results:
                        desc = res.get("description", "").lower()
                        # Игнорируем явные "family name"
                        if "family name" in desc or "фамилия" in desc:
                            continue
                        # Приоритет политикам
                        if "president" in desc or "politician" in desc or "президент" in desc or "политик" in desc:
                            selected_res_item = res
                            break
                
                # 2. Если не нашли, берем первый, который не "family name"
                if not selected_res_item:
                    for res in search_results:
                        desc = res.get("description", "").lower()
                        if "family name" not in desc and "фамилия" not in desc:
                            selected_res_item = res
                            break
                
                # 3. Fallback
                if not selected_res_item:
                    selected_res_item = search_results[0]
                
                # Получаем полную инфу
                qid = selected_res_item.get("id")
                best_match = self.get_entity_info(qid, language)

            if best_match:
                # Финальная проверка: исключаем географические объекты и еду, если искали человека
                # Это случается, если expected_type был Person, но Strict Check не сработал (например, нет Q5),
                # и свалились в эвристику, которая выбрала первый результат.
                
                instances = best_match.get("metadata", {}).get("instance_of_qids", [])
                
                should_discard = False
                
                if expected_type in ["person", "politician"]:
                    # Проверяем на "запрещенные" типы для людей
                    # Q2095 = food (poutine)
                    # Q486972 = human settlement (khutor, village, etc.)
                    # Q101352 = family name (уже проверяли, но на всякий случай)
                    
                    # Получаем рекурсивно типы? Нет, это долго. Проверим прямые совпадения.
                    # Q15865662 (хутор) -> Q2023000 -> Q486972. Wikidata сервис возвращает прямые P31.
                    # Для Хутора Зеленский P31 = Q2023000 (хутор).
                    
                    bad_types = {
                        "Q2095", # food
                        "Q486972", "Q2023000", "Q532", "Q15865662", # settlements/places
                        "Q101352", # family name
                        "Q56061" # administrative territorial entity
                    }
                    
                    if any(bt in instances for bt in bad_types):
                        should_discard = True
                        logger.debug(f"Discarding result {best_match.get('qid')} (bad type for Person)")

                if not should_discard:
                    self._set_cached(cache_key, best_match)
                    return best_match
            
            return None
            
        except requests.RequestException as e:
            logger.warning(f"Wikidata search request failed for '{name}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Wikidata search for '{name}': {e}")
            return None
    
    def get_entity_info(
        self,
        qid: str,
        language: str = "ru"
    ) -> Optional[Dict]:
        """
        Получить полную информацию о сущности по QID.
        
        Args:
            qid: QID сущности (например, "Q7747")
            language: Язык для получения меток и описаний
            
        Returns:
            Словарь с полями:
            - qid: QID
            - canonical_name: каноническое имя
            - aliases: список алиасов на разных языках
            - metadata: метаданные (должности, страны, даты рождения и т.д.)
        """
        if not qid or not qid.startswith("Q"):
            return None
        
        # Проверяем кэш
        cache_key = f"entity:{qid}:{language}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.debug(f"Cache hit for QID {qid}")
            return cached
        
        try:
            # Получение информации через Wikidata API
            params = {
                "action": "wbgetentities",
                "ids": qid,
                "languages": f"{language}|en",  # Получаем на русском и английском
                "props": "labels|aliases|claims|descriptions",
                "format": "json"
            }
            
            headers = {
                'User-Agent': 'SDAS Actor Canonicalization Service/1.0 (https://github.com/your-repo)'
            }
            response = requests.get(self.WIKIDATA_API_URL, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            entities = data.get("entities", {})
            
            if qid not in entities:
                return None
            
            entity = entities[qid]
            
            # Извлекаем каноническое имя
            labels = entity.get("labels", {})
            canonical_name = None
            
            # Приоритет английскому языку для стандартизации графа (латиница)
            if "en" in labels:
                canonical_name = labels["en"].get("value")
            elif language in labels:
                canonical_name = labels[language].get("value")
            elif labels:
                # Берем первое доступное
                canonical_name = list(labels.values())[0].get("value")
            
            if not canonical_name:
                return None
            
            # Извлекаем алиасы
            aliases = []
            aliases_data = entity.get("aliases", {})
            
            # Алиасы на русском
            if language in aliases_data:
                for alias_entry in aliases_data[language]:
                    alias_name = alias_entry.get("value")
                    if alias_name and alias_name != canonical_name:
                        aliases.append({
                            "name": alias_name,
                            "type": "alias",
                            "language": language
                        })
            
            # Алиасы на английском
            if "en" in aliases_data:
                for alias_entry in aliases_data["en"]:
                    alias_name = alias_entry.get("value")
                    if alias_name and alias_name != canonical_name:
                        # Проверяем на дубликаты
                        if not any(a["name"].lower() == alias_name.lower() for a in aliases):
                            aliases.append({
                                "name": alias_name,
                                "type": "alias",
                                "language": "en"
                            })
            
            # Извлекаем метаданные
            metadata = self._extract_metadata(entity, language)
            
            # Определяем тип актора
            inferred_type = self._determine_actor_type(metadata)
            
            result = {
                "qid": qid,
                "canonical_name": canonical_name,
                "aliases": aliases,
                "metadata": metadata,
                "type": inferred_type
            }
            
            # Сохраняем в кэш
            self._set_cached(cache_key, result)
            
            return result
            
        except requests.RequestException as e:
            logger.warning(f"Wikidata entity request failed for {qid}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting entity info for {qid}: {e}")
            return None
    
    def _determine_actor_type(self, metadata: Dict) -> Optional[ActorType]:
        """
        Определить тип актора на основе метаданных (P31, P106).
        """
        # Check P106 (Occupation) - Priority 1
        occupations = metadata.get("occupation_qids", [])
        for qid in occupations:
            if qid in self.TYPE_MAPPINGS:
                return self.TYPE_MAPPINGS[qid]
        
        # Check P31 (Instance of) - Priority 2
        instances = metadata.get("instance_of_qids", [])
        
        # First pass: Look for SPECIFIC types (excluding generic Human/Organization)
        # Q5 = Human, Q43229 = Organization
        generic_qids = {"Q5", "Q43229"}
        
        for qid in instances:
            if qid in self.TYPE_MAPPINGS and qid not in generic_qids:
                return self.TYPE_MAPPINGS[qid]
                
        # Second pass: Allow generic types
        for qid in instances:
            if qid in self.TYPE_MAPPINGS:
                return self.TYPE_MAPPINGS[qid]
        
        return None

    def _extract_metadata(self, entity: Dict, language: str) -> Dict:
        """
        Извлечь метаданные из данных Wikidata.
        
        Args:
            entity: Данные сущности из Wikidata API
            language: Язык для получения меток
            
        Returns:
            Словарь с метаданными
        """
        metadata = {}
        claims = entity.get("claims", {})

        # Instance of (P31)
        instance_of_qids = []
        if "P31" in claims:
            for claim in claims["P31"]:
                mainsnak = claim.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                if datavalue.get("type") == "wikibase-entityid":
                    qid = datavalue.get("value", {}).get("id")
                    if qid:
                        instance_of_qids.append(qid)
        metadata["instance_of_qids"] = instance_of_qids

        # Occupation (P106)
        occupation_qids = []
        if "P106" in claims:
            for claim in claims["P106"]:
                mainsnak = claim.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                if datavalue.get("type") == "wikibase-entityid":
                    qid = datavalue.get("value", {}).get("id")
                    if qid:
                        occupation_qids.append(qid)
        metadata["occupation_qids"] = occupation_qids
        
        # Должности (P39 - position held)
        positions = []
        if "P39" in claims:
            for claim in claims["P39"]:
                mainsnak = claim.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                if datavalue.get("type") == "wikibase-entityid":
                    position_qid = datavalue.get("value", {}).get("id")
                    if position_qid:
                        # Получаем название должности
                        position_name = self._get_label_for_qid(position_qid, language)
                        if position_name:
                            positions.append(position_name)
        
        if positions:
            metadata["positions"] = positions
        
        # Страна гражданства (P27 - country of citizenship)
        countries = []
        if "P27" in claims:
            for claim in claims["P27"]:
                mainsnak = claim.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                if datavalue.get("type") == "wikibase-entityid":
                    country_qid = datavalue.get("value", {}).get("id")
                    if country_qid:
                        country_name = self._get_label_for_qid(country_qid, language)
                        if country_name:
                            countries.append(country_name)
        
        if countries:
            metadata["countries"] = countries
            metadata["country"] = countries[0]  # Основная страна
        
        # Дата рождения (P569)
        if "P569" in claims:
            birth_claim = claims["P569"][0]
            mainsnak = birth_claim.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            if datavalue.get("type") == "time":
                birth_time = datavalue.get("value", {}).get("time")
                if birth_time:
                    metadata["birth_date"] = birth_time
        
        # Описание
        descriptions = entity.get("descriptions", {})
        if language in descriptions:
            metadata["description"] = descriptions[language].get("value")
        elif "en" in descriptions:
            metadata["description"] = descriptions["en"].get("value")
        
        return metadata
    
    def _get_label_for_qid(self, qid: str, language: str) -> Optional[str]:
        """
        Получить метку (название) для QID.
        
        Args:
            qid: QID сущности
            language: Язык метки
            
        Returns:
            Название сущности или None
        """
        # Проверяем кэш
        cache_key = f"label:{qid}:{language}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            params = {
                "action": "wbgetentities",
                "ids": qid,
                "languages": f"{language}|en",
                "props": "labels",
                "format": "json"
            }
            
            headers = {
                'User-Agent': 'SDAS Actor Canonicalization Service/1.0 (https://github.com/your-repo)'
            }
            response = requests.get(self.WIKIDATA_API_URL, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            entities = data.get("entities", {})
            
            if qid in entities:
                labels = entities[qid].get("labels", {})
                if language in labels:
                    label = labels[language].get("value")
                    self._set_cached(cache_key, label)
                    return label
                elif "en" in labels:
                    label = labels["en"].get("value")
                    self._set_cached(cache_key, label)
                    return label
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to get label for {qid}: {e}")
            return None

