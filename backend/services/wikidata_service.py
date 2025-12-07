"""
Сервис для работы с Wikidata API.
Используется для канонизации имен акторов и получения метаданных.
"""
import requests
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class WikidataService:
    """
    Сервис для поиска и получения информации о сущностях из Wikidata.
    """
    
    WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
    WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
    
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
        limit: int = 5
    ) -> Optional[Dict]:
        """
        Поиск сущности в Wikidata по имени.
        
        Args:
            name: Имя для поиска
            language: Язык поиска ('ru' или 'en')
            limit: Максимальное количество результатов
            
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
        
        # Проверяем кэш
        cache_key = f"search:{language}:{name.lower()}"
        cached = self._get_cached(cache_key)
        if cached:
            logger.debug(f"Cache hit for '{name}'")
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
                # Кэшируем отрицательный результат на меньшее время
                self._set_cached(cache_key, None)
                return None
            
            # Берем первый результат (обычно самый релевантный)
            result = search_results[0]
            qid = result.get("id")
            
            if not qid:
                return None
            
            # Получаем полную информацию о сущности
            entity_info = self.get_entity_info(qid, language)
            
            if entity_info:
                # Сохраняем в кэш
                self._set_cached(cache_key, entity_info)
                return entity_info
            
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
            if language in labels:
                canonical_name = labels[language].get("value")
            elif "en" in labels:
                canonical_name = labels["en"].get("value")
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
            
            result = {
                "qid": qid,
                "canonical_name": canonical_name,
                "aliases": aliases,
                "metadata": metadata
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

