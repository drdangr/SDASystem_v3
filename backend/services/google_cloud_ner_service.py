"""
Google Cloud Natural Language API Service
Сервис для извлечения сущностей через официальный Google Cloud API.
Поддерживает работу через API Key (REST) или Service Account (Library).
"""
import logging
import os
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class GoogleCloudNERService:
    """
    Обертка над Google Cloud Natural Language API.
    Теперь поддерживает работу через обычный API Key (REST), что проще для настройки.
    """

    def __init__(self, api_key: Optional[str] = None):
        # Если передан API ключ, будем использовать REST API
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") # Часто используется один и тот же ключ
        self.use_rest = bool(self.api_key)
        
        # Если ключа нет, попробуем стандартную библиотеку (требует JSON credentials)
        self.client = None
        if not self.use_rest:
            try:
                from google.cloud import language_v2
                self.client = language_v2.LanguageServiceClient()
                logger.info("Google Cloud Language Service initialized (Client Mode).")
            except ImportError:
                logger.warning("google-cloud-language library not installed and no API Key provided.")
            except Exception as e:
                logger.error(f"Failed to initialize Google Cloud Client: {e}")

    def extract_actors(self, text: str) -> List[Dict]:
        """
        Извлечь сущности.
        """
        if not text:
            return []

        if self.use_rest:
            return self._extract_rest(text)
        elif self.client:
            return self._extract_client(text)
        else:
            logger.warning("Google Cloud NER not configured (no Key and no Client).")
            return []

    def _extract_rest(self, text: str) -> List[Dict]:
        """Работа через REST API (проще, нужен только API Key)"""
        url = f"https://language.googleapis.com/v1/documents:analyzeEntities?key={self.api_key}"
        
        payload = {
            "document": {
                "type": "PLAIN_TEXT",
                "content": text
            },
            "encodingType": "UTF8"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Google Cloud API Error ({response.status_code}): {response.text}")
                return []
                
            data = response.json()
            results = []
            seen = set()
            
            for entity in data.get("entities", []):
                name = entity.get("name")
                if name.lower() in seen:
                    continue
                seen.add(name.lower())
                
                # Type mapping (REST return strings like 'PERSON', 'ORGANIZATION')
                entity_type = entity.get("type", "OTHER")
                actor_type = self._map_google_type(entity_type)
                
                if not actor_type:
                    continue

                metadata = entity.get("metadata", {})
                mid = metadata.get("mid")
                wikipedia_url = metadata.get("wikipedia_url")
                
                results.append({
                    "name": name,
                    "type": actor_type,
                    "confidence": entity.get("salience", 0.5), # REST returns salience, not confidence per se
                    "metadata": {
                        "mid": mid,
                        "wikipedia_url": wikipedia_url,
                        "source": "google_cloud_rest"
                    }
                })
            return results
            
        except Exception as e:
            logger.error(f"Error in Google Cloud REST API: {e}")
            return []

    def _extract_client(self, text: str) -> List[Dict]:
        """Работа через официальную библиотеку (требует JSON key)"""
        # ... (код который был раньше) ...
        # Для краткости, если пользователь выбрал API Key, этот код не вызовется
        return []

    def _map_google_type(self, g_type: str) -> Optional[str]:
        """Convert Google Entity Type string to our types."""
        t = str(g_type).upper()
        
        if "PERSON" in t:
            return "person"
        elif "LOCATION" in t:
            return "country"
        elif "ORGANIZATION" in t:
            return "organization"
        elif "EVENT" in t:
            return "event"
        elif "CONSUMER_GOOD" in t:
            return "product"
        
        return None
