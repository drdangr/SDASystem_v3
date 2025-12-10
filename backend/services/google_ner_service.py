"""
Google NER Service
Альтернативная реализация NER на базе Google Gemini.
Выполняет извлечение и очистку (канонизацию) сущностей в один проход через LLM,
используя знания модели вместо Wikidata/Spacy.
"""
import json
import logging
import re
from typing import List, Dict, Optional
from backend.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class GoogleNERService:
    """
    NER сервис, полностью основанный на Google Gemini.
    """

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    def load_gazetteer(self, actors: List) -> None:
        """
        Загрузить известных акторов.
        Для GoogleNERService это пока не используется (LLM работает без контекста),
        но метод нужен для совместимости интерфейса.
        """
        pass

    def extract_actors(self, text: str, **kwargs) -> List[Dict]:
        """
        Извлечение и очистка акторов из текста.
        
        Args:
            text: Текст новости
            **kwargs: Аргументы для совместимости (use_llm, thresholds и т.д. игнорируются)

        Returns:
            List[Dict]: Список сущностей с ключами:
                - name: каноническое имя (очищенное)
                - original_name: как в тексте
                - type: тип сущности
                - confidence: уверенность
                - description: краткое описание (для проверки)
        """
        prompt = (
            "Analyze the following news text and extract named entities (Actors). "
            "Perform TWO steps in one go:\n"
            "1. EXTRACTION: Find all significant politicians, countries, companies, organizations, and persons.\n"
            "2. CLEANING & CANONICALIZATION: Return the CANONICAL name for each entity in LATIN script.\n\n"
            "Canonicalization rules:\n"
            "   - Use well-known English names if they exist:\n"
            "     'Putin', 'Путин' -> 'Vladimir Putin'\n"
            "     'США', 'Америка' -> 'United States'\n"
            "     'Белый дом' -> 'White House'\n"
            "   - For NAMES of persons, companies, places without known English equivalent:\n"
            "     Use PHONETIC transliteration (Иванов -> Ivanov, Газпром -> Gazprom)\n"
            "   - For TITLES, positions, organization types:\n"
            "     TRANSLATE to English (Министерство обороны -> Ministry of Defense)\n"
            "   - Resolve genitive/declined forms to Nominative case.\n\n"
            "Return a JSON list of objects with these fields:\n"
            "- 'canonical_name': Standardized name in LATIN script (English or transliterated).\n"
            "- 'original_name': The exact text fragment found in source (any language).\n"
            "- 'type': One of ['politician', 'person', 'company', 'country', 'organization', 'int_org', 'government'].\n"
            "- 'confidence': Float 0.0-1.0.\n"
            "- 'description': Short 3-5 word identity in English.\n\n"
            "Rules:\n"
            "- EXTRACT ALL ENTITIES found in text. Be exhaustive.\n"
            "- ALL canonical_name MUST use LATIN script (a-z, A-Z). Never Cyrillic or other scripts.\n"
            "- Skip generic terms like 'president' alone, 'ministry' without country.\n"
            "- Output JSON ONLY. No markdown fences.\n\n"
            f"Text:\n{text[:15000]}"
        )

        raw_response = self.llm._run(prompt, temperature=0.1) # Low temp for precision
        
        # Parse JSON
        try:
            # Clean markdown if present
            cleaned = self.llm._strip_code_fences(raw_response)
            data = json.loads(cleaned)
            
            if isinstance(data, list):
                # Post-processing normalization
                results = []
                for item in data:
                    if not item.get('canonical_name'):
                        continue
                    
                    # Ensure fields exist
                    item['name'] = item['canonical_name'] # map to standard interface
                    if 'type' not in item:
                        item['type'] = 'organization'
                    
                    results.append(item)
                return results
            else:
                logger.warning(f"Google NER returned non-list JSON: {str(data)[:100]}")
                return []
                
        except json.JSONDecodeError:
            logger.error(f"Failed to parse Google NER response. Raw: {raw_response[:200]}...")
            return []
        except Exception as e:
            logger.error(f"Error in Google NER: {e}")
            return []
