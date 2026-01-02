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
            "- Return up to 15 entities (focus on the most important).\n"
            "- You MUST return a JSON ARRAY (even if it has only 1 element). Never return a single JSON object.\n"
            "- If the text mentions Zelensky/Zelenskyy/Зеленський/Зеленский, Putin/Путін/Путин, Biden/Байден, you MUST include them.\n"
            "- Also include key implied state/org actors when present in the text: Ukraine, Russia, United States, NATO, United Nations, White House, Kremlin.\n"
            "- ALL canonical_name MUST use LATIN script (a-z, A-Z). Never Cyrillic or other scripts.\n"
            "- Skip generic terms like 'president' alone, 'ministry' without country.\n"
            "- Output JSON ONLY. No markdown fences.\n\n"
            f"Text:\n{text[:15000]}"
        )

        raw_response = self.llm._run(
            prompt,
            temperature=0.0,  # максимально детерминированно, чтобы JSON не разваливался
            max_output_tokens=2048,  # JSON может быть длинным; избегаем обрезаний
        )
        
        # Parse JSON
        try:
            # Clean markdown if present
            cleaned = self.llm._strip_code_fences(raw_response)

            def _try_parse(s: str):
                return json.loads(s)

            data = None
            try:
                data = _try_parse(cleaned)
            except Exception:
                # Fallback 1: try raw (sometimes fences already stripped or formatting differs)
                try:
                    data = _try_parse(raw_response)
                except Exception:
                    # Fallback 2: extract first JSON array/object from the text
                    # Handles cases where model adds commentary after JSON.
                    m = re.search(r"(\[[\s\S]*\])", cleaned)
                    if not m:
                        m = re.search(r"(\{[\s\S]*\})", cleaned)
                    if m:
                        data = _try_parse(m.group(1))
                    else:
                        raise
            
            # Иногда модель возвращает один объект вместо массива — нормализуем
            if isinstance(data, dict):
                data = [data]

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
        except ValueError as e:
            # Специальная обработка ошибок API ключа (перебрасываем дальше)
            error_str = str(e)
            if "API КЛЮЧА" in error_str or "leaked" in error_str.lower():
                logger.error(f"❌ Google NER: {error_str}")
                print(f"\n⚠️  Google NER Service не может работать: {error_str}\n")
            raise
        except Exception as e:
            error_str = str(e).lower()
            # Проверяем на ошибку API ключа в сообщении об ошибке
            if "403" in error_str or "forbidden" in error_str or "leaked" in error_str:
                error_msg = (
                    "❌ ОШИБКА API КЛЮЧА в Google NER: Ваш ключ Google Gemini недействителен или заблокирован.\n"
                    "📝 РЕШЕНИЕ: Получите новый API ключ на https://aistudio.google.com/app/apikey\n"
                    "   Обновите GEMINI_API_KEY в файле .env и перезапустите сервер."
                )
                logger.error(error_msg)
                print(f"\n{error_msg}\n")
                return []
            logger.error(f"Error in Google NER: {e}")
            return []
