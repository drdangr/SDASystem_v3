#!/usr/bin/env python3
"""
Скрипт сравнения двух систем извлечения NER:
1. Гибридная (существующая): Spacy + LLM Fallback + Wikidata Canonicalization
2. Google (новая): Pure Gemini Extraction & Cleaning

Запускает обе системы на выборке новостей и выводит сравнительную таблицу.
"""
import sys
import json
import logging
import time
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Load env vars from root .env
root_dir = Path(__file__).parent.parent
load_dotenv(root_dir / ".env")

# Добавляем корень проекта в путь
sys.path.append(str(root_dir))

from backend.services.llm_service import LLMService
from backend.services.ner_spacy_service import create_hybrid_ner_service
from backend.services.actor_canonicalization_service import ActorCanonicalizationService
from backend.services.google_ner_service import GoogleNERService
from backend.services.google_cloud_ner_service import GoogleCloudNERService
from backend.models.entities import News, Actor

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Отключаем лишние логи
logging.getLogger("backend.services.llm_service").setLevel(logging.WARNING)
logging.getLogger("backend.services.ner_spacy_service").setLevel(logging.WARNING)
logging.getLogger("backend.services.google_cloud_ner_service").setLevel(logging.WARNING)

def load_sample_news(limit: int = 3) -> List[News]:
    """Загрузить несколько новостей для теста"""
    news_file = Path("data/news.json")
    if not news_file.exists():
        logger.error("data/news.json not found")
        return []
    
    with open(news_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Берем разные новости (с начала, середины и конца если возможно)
    samples = []
    if len(data) > 0: samples.append(data[0])
    if len(data) > 10: samples.append(data[10])
    if len(data) > 20: samples.append(data[20])
    
    # Если мало, просто берем первые limit
    if len(samples) < limit:
        samples = data[:limit]
        
    return [News(**item) for item in samples[:limit]]

class MockGoogleLLM(LLMService):
    """Mock LLM that returns prepared JSON for specific news"""
    def _run(self, prompt: str, **overrides) -> str:
        # Simple heuristic to match news content in prompt
        if "Russia Criticizes NATO" in prompt or "NATO's decision" in prompt:
            return json.dumps([
                {"canonical_name": "Russia", "type": "country", "confidence": 0.99, "original_name": "Russia"},
                {"canonical_name": "North Atlantic Treaty Organization", "type": "int_org", "confidence": 0.99, "original_name": "NATO"},
                {"canonical_name": "Ukraine", "type": "country", "confidence": 0.95, "original_name": "Ukraine"},
                {"canonical_name": "Vladimir Putin", "type": "politician", "confidence": 0.99, "original_name": "Vladimir Putin"}
            ])
        elif "UN Calls for Peace" in prompt or "United Nations called" in prompt:
            return json.dumps([
                {"canonical_name": "United Nations", "type": "int_org", "confidence": 0.99, "original_name": "United Nations"},
                {"canonical_name": "Ukraine", "type": "country", "confidence": 0.95, "original_name": "Ukraine"}
            ])
        elif "Climate Summit" in prompt or "Global Climate Summit" in prompt:
            return json.dumps([
                {"canonical_name": "Joe Biden", "type": "politician", "confidence": 0.98, "original_name": "Joe Biden"},
                {"canonical_name": "Xi Jinping", "type": "politician", "confidence": 0.98, "original_name": "Xi Jinping"},
                {"canonical_name": "Ursula von der Leyen", "type": "politician", "confidence": 0.98, "original_name": "Ursula von der Leyen"}
            ])
        return "[]"

class MockGoogleCloudNER(GoogleCloudNERService):
    """Mock for Google Cloud Natural Language API"""
    def __init__(self):
        self.client = True # Fake it
        
    def extract_actors(self, text: str) -> List[Dict]:
        # Emulate strict API behavior (no context awareness, just entities)
        if "Russia Criticizes NATO" in text:
            return [
                {"name": "NATO", "type": "organization", "metadata": {"mid": "/m/059r2"}},
                {"name": "Russia", "type": "country", "metadata": {"mid": "/m/06bnz"}},
                {"name": "Ukraine", "type": "country", "metadata": {"mid": "/m/07t21"}},
                {"name": "Vladimir Putin", "type": "person", "metadata": {"mid": "/m/0pc_x"}},
                {"name": "conflict", "type": "event", "metadata": {}} # Often extracts generic events
            ]
        elif "UN Calls for Peace" in text:
            return [
                {"name": "United Nations", "type": "organization", "metadata": {"mid": "/m/07f35"}},
                {"name": "Ukraine", "type": "country", "metadata": {"mid": "/m/07t21"}},
                {"name": "organization", "type": "organization", "metadata": {}} # Generic word
            ]
        elif "Climate Summit" in text:
             return [
                {"name": "Global Climate Summit", "type": "event", "metadata": {}},
                {"name": "Joe Biden", "type": "person", "metadata": {"mid": "/m/012gx2"}},
                {"name": "Xi Jinping", "type": "person", "metadata": {"mid": "/m/0q9k6"}},
                {"name": "Ursula von der Leyen", "type": "person", "metadata": {"mid": "/m/0x45_"}},
                {"name": "Today", "type": "organization", "metadata": {}} # Common error for capitalized words
            ]
        return []

def run_hybrid_system(text: str, llm_service: LLMService) -> List[Dict]:
    """Запуск текущей гибридной системы"""
    # 1. Init services
    hybrid_ner = create_hybrid_ner_service(llm_service, use_spacy=True)
    canon_service = ActorCanonicalizationService(use_wikidata=True, use_lemmatization=True)
    
    start_time = time.time()
    
    # 2. Extract
    extracted = hybrid_ner.extract_actors(
        text, 
        use_llm=True, 
        use_llm_for_low_confidence=True
    )
    
    # 3. Canonicalize
    canonicalized = canon_service.canonicalize_batch(extracted)
    
    duration = time.time() - start_time
    
    # Format result
    results = []
    for item in canonicalized:
        results.append({
            "name": item.get("canonical_name") or item.get("name"),
            "type": item.get("type"),
            "confidence": item.get("confidence", 0.0),
            "source": "hybrid"
        })
    
    return results, duration

def run_google_system(text: str, llm_service: LLMService) -> List[Dict]:
    """Запуск новой Google NER системы"""
    try:
        google_ner = GoogleNERService(llm_service)
        
        start_time = time.time()
        extracted = google_ner.extract_actors(text)
        duration = time.time() - start_time
        
        # Format result (already cleaned by LLM)
        results = []
        for item in extracted:
            results.append({
                "name": item.get("name"), # canonical name from GoogleNER
                "type": item.get("type"),
                "confidence": item.get("confidence", 0.0),
                "source": "google"
            })
        
        return results, duration
    except Exception as e:
        logger.error(f"Gemini API failed: {e}")
        return [], 0.0

def run_google_cloud_system(text: str) -> List[Dict]:
    """Запуск официального Google Cloud API (через API Key)"""
    # Теперь сервис сам найдет ключ в GEMINI_API_KEY
    service = GoogleCloudNERService()
    
    start_time = time.time()
    extracted = service.extract_actors(text)
    duration = time.time() - start_time
    
    results = []
    for item in extracted:
        results.append({
            "name": item.get("name"),
            "type": item.get("type"),
            "confidence": item.get("confidence", 0.0),
            "source": "google_cloud"
        })
    return results, duration

def print_comparison(news_title: str, hybrid_res: List[Dict], google_res: List[Dict], cloud_res: List[Dict], t_hybrid: float, t_google: float, t_cloud: float):
    """Вывод результатов сравнения"""
    print(f"\n{'='*100}")
    print(f"NEWS: {news_title}")
    print(f"{'='*100}")
    
    print(f"{'METRIC':<20} | {'HYBRID':<20} | {'GEMINI (LLM)':<20} | {'CLOUD API':<20}")
    print(f"{'-'*20}-+-{'-'*20}-+-{'-'*20}-+-{'-'*20}")
    print(f"{'Time (sec)':<20} | {t_hybrid:<20.2f} | {t_google:<20.2f} | {t_cloud:<20.2f}")
    print(f"{'Entities Found':<20} | {len(hybrid_res):<20} | {len(google_res):<20} | {len(cloud_res):<20}")
    
    # Collect all unique names
    hybrid_names = sorted([f"{r['name']} ({r['type']})" for r in hybrid_res])
    google_names = sorted([f"{r['name']} ({r['type']})" for r in google_res])
    cloud_names = sorted([f"{r['name']} ({r['type']})" for r in cloud_res])
    
    max_len = max(len(hybrid_names), len(google_names), len(cloud_names))
    
    print(f"\n{'HYBRID':<32} | {'GEMINI (LLM)':<32} | {'CLOUD API':<32}")
    print(f"{'-'*32}-+-{'-'*32}-+-{'-'*32}")
    
    for i in range(max_len):
        h_val = hybrid_names[i] if i < len(hybrid_names) else ""
        g_val = google_names[i] if i < len(google_names) else ""
        c_val = cloud_names[i] if i < len(cloud_names) else ""
        print(f"{h_val:<32} | {g_val:<32} | {c_val:<32}")


def main():
    print("Initializing services...")
    llm_service = LLMService()
    
    # Check if we have API key
    if not llm_service.api_key:
        print("WARNING: No GEMINI_API_KEY found. Using MockGoogleLLM for demonstration.")
        llm_service_google = MockGoogleLLM() # Use special mock for Google NER
    else:
        print("Using REAL Gemini API Key.")
        llm_service_google = llm_service

    news_items = load_sample_news(limit=3)
    if not news_items:
        print("No news found.")
        return

    print(f"Loaded {len(news_items)} news items for comparison.")
    
    for news in news_items:
        text = f"{news.title}\n{news.full_text}"
        
        # Run Hybrid (uses default LLMService which falls back to its own mock/spacy)
        h_res, h_time = run_hybrid_system(text, llm_service)
        
        # Run Google (uses real or smart-mock LLM)
        g_res, g_time = run_google_system(text, llm_service_google)
        
        # Run Cloud API (uses real or smart-mock)
        c_res, c_time = run_google_cloud_system(text)
        
        print_comparison(news.title, h_res, g_res, c_res, h_time, g_time, c_time)

if __name__ == "__main__":
    main()

