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
            "2. CLEANING & CANONICALIZATION: Return the CANONICAL name for each entity. \n"
            "   - E.g. convert 'Putin' -> 'Vladimir Putin'\n"
            "   - Convert 'US', 'USA', 'America' -> 'United States'\n"
            "   - Convert 'Zelenskyy' -> 'Volodymyr Zelenskyy'\n"
            "   - Convert 'RF' -> 'Russia'\n"
            "   - Resolve genitive/declined forms (Russian specific) to Nominative case (e.g. 'Москвы' -> 'Москва').\n\n"
            "Return a JSON list of objects with these fields:\n"
            "- 'canonical_name': The standardized, full name (in the same language as the text, usually Russian or English).\n"
            "- 'original_name': The exact text fragment found in source.\n"
            "- 'type': One of ['politician', 'person', 'company', 'country', 'organization', 'int_org', 'government'].\n"
            "- 'confidence': Float 0.0-1.0.\n"
            "- 'description': Short 3-5 word identity check (e.g. 'President of Russia').\n\n"
            "Rules:\n"
            "- EXTRACT ALL ENTITIES found in text, do not limit quantity. Be exhaustive.\n"
            "- Skip generic terms like 'president' (unless used as title), 'ministry' (without specific country).\n"
            "- Output JSON ONLY. No markdown fences.\n\n"
            f"Text:\n{text[:15000]}"  # Limit text length just in case
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
