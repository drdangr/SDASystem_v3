"""
Тест для сравнения производительности LLM vs Hybrid (spaCy + LLM) подхода.

Запуск:
    pytest tests/test_hybrid_ner_comparison.py -v -s
"""
import os
import json
import time
from pathlib import Path
from typing import Dict, List

import pytest

from backend.services.llm_service import LLMService
from backend.services.ner_spacy_service import HybridNERService
from backend.models.entities import Actor, ActorType


PROJECT_ROOT = Path(__file__).parent.parent
NEWS_FILE = PROJECT_ROOT / "data" / "news.json"
ACTORS_FILE = PROJECT_ROOT / "data" / "actors.json"


def load_actors() -> List[Actor]:
    """Загрузить акторов из файла"""
    if not ACTORS_FILE.exists():
        return []
    
    with open(ACTORS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    actors = []
    for item in data:
        actor = Actor(
            id=item["id"],
            canonical_name=item["canonical_name"],
            actor_type=ActorType(item["actor_type"]),
            aliases=item.get("aliases", [])
        )
        actors.append(actor)
    
    return actors


def load_test_news() -> List[Dict]:
    """Загрузить тестовые новости"""
    if not NEWS_FILE.exists():
        return []
    
    with open(NEWS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def llm_service():
    """Создать LLM сервис"""
    api_key = os.getenv("GEMINI_API_KEY")
    use_mock = os.getenv("LLM_FORCE_MOCK") == "1" or not api_key
    
    service = LLMService(
        api_key=api_key,
        use_mock=use_mock,
        temperature=0.3
    )
    return service


@pytest.fixture
def hybrid_service(llm_service):
    """Создать гибридный сервис"""
    actors = load_actors()
    service = HybridNERService(llm_service, use_spacy=True)
    if actors:
        service.load_gazetteer(actors)
    return service


def test_single_news_comparison(llm_service, hybrid_service):
    """Сравнить результаты для одной новости"""
    news_list = load_test_news()
    if not news_list:
        pytest.skip("Нет тестовых новостей")
    
    # Взять первую новость с текстом
    test_news = news_list[0]
    text = f"{test_news.get('title', '')}\n{test_news.get('summary', '')}\n{test_news.get('full_text', '')}"
    
    print(f"\n{'='*80}")
    print(f"СРАВНЕНИЕ: {test_news.get('title', 'Unknown')}")
    print(f"{'='*80}\n")
    print(f"Текст: {text[:200]}...\n")
    
    # Метод 1: Только LLM
    print("-" * 80)
    print("1. ТОЛЬКО LLM")
    print("-" * 80)
    start_time = time.time()
    llm_actors = llm_service.extract_actors(text)
    llm_time = time.time() - start_time
    
    print(f"Время: {llm_time:.2f} сек")
    print(f"Найдено акторов: {len(llm_actors)}")
    for actor in llm_actors[:5]:
        print(f"  - {actor.get('name')} ({actor.get('type')}, confidence: {actor.get('confidence', 0):.2f})")
    
    # Метод 2: Гибридный (spaCy + LLM)
    print("\n" + "-" * 80)
    print("2. ГИБРИДНЫЙ (spaCy + LLM)")
    print("-" * 80)
    
    try:
        start_time = time.time()
        hybrid_actors = hybrid_service.extract_actors(text, use_llm=True)
        hybrid_time = time.time() - start_time
        
        print(f"Время: {hybrid_time:.2f} сек")
        print(f"Найдено акторов: {len(hybrid_actors)}")
        for actor in hybrid_actors[:5]:
            print(f"  - {actor.get('name')} ({actor.get('type')}, confidence: {actor.get('confidence', 0):.2f})")
        
        # Сравнение
        print("\n" + "-" * 80)
        print("СРАВНЕНИЕ")
        print("-" * 80)
        print(f"Время LLM: {llm_time:.2f} сек")
        print(f"Время Hybrid: {hybrid_time:.2f} сек")
        if hybrid_time > 0:
            speedup = llm_time / hybrid_time
            print(f"Ускорение: {speedup:.2f}x {'(быстрее)' if speedup > 1 else '(медленнее)'}")
        
        print(f"\nАкторов найдено LLM: {len(llm_actors)}")
        print(f"Акторов найдено Hybrid: {len(hybrid_actors)}")
        
        # Сравнение найденных акторов
        llm_names = {a['name'].lower() for a in llm_actors}
        hybrid_names = {a['name'].lower() for a in hybrid_actors}
        
        common = llm_names & hybrid_names
        only_llm = llm_names - hybrid_names
        only_hybrid = hybrid_names - llm_names
        
        print(f"\nОбщих акторов: {len(common)}")
        if common:
            print(f"  {', '.join(list(common)[:5])}")
        
        if only_llm:
            print(f"\nТолько в LLM: {len(only_llm)}")
            print(f"  {', '.join(list(only_llm)[:5])}")
        
        if only_hybrid:
            print(f"\nТолько в Hybrid: {len(only_hybrid)}")
            print(f"  {', '.join(list(only_hybrid)[:5])}")
        
    except Exception as e:
        print(f"Ошибка при использовании гибридного метода: {e}")
        print("Продолжаем только с LLM")
    
    print("=" * 80 + "\n")


def test_multiple_news_comparison(llm_service, hybrid_service):
    """Сравнить результаты для нескольких новостей"""
    news_list = load_test_news()
    if not news_list:
        pytest.skip("Нет тестовых новостей")
    
    # Взять первые 3 новости для теста
    test_news_list = news_list[:3]
    
    print(f"\n{'='*80}")
    print(f"СРАВНЕНИЕ ДЛЯ {len(test_news_list)} НОВОСТЕЙ")
    print(f"{'='*80}\n")
    
    llm_times = []
    hybrid_times = []
    llm_counts = []
    hybrid_counts = []
    
    for i, news in enumerate(test_news_list, 1):
        text = f"{news.get('title', '')}\n{news.get('summary', '')}\n{news.get('full_text', '')}"
        
        print(f"Новость {i}: {news.get('title', 'Unknown')[:60]}...")
        
        # LLM
        start = time.time()
        llm_actors = llm_service.extract_actors(text)
        llm_time = time.time() - start
        llm_times.append(llm_time)
        llm_counts.append(len(llm_actors))
        
        # Hybrid
        try:
            start = time.time()
            hybrid_actors = hybrid_service.extract_actors(text, use_llm=True)
            hybrid_time = time.time() - start
            hybrid_times.append(hybrid_time)
            hybrid_counts.append(len(hybrid_actors))
        except Exception as e:
            print(f"  Hybrid ошибка: {e}")
            hybrid_times.append(llm_time)  # Fallback
            hybrid_counts.append(len(llm_actors))
        
        # Небольшая задержка чтобы не превысить rate limits
        time.sleep(0.5)
    
    # Итоги
    print("\n" + "=" * 80)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 80)
    print(f"\nОбработано новостей: {len(test_news_list)}")
    print(f"\nLLM:")
    print(f"  Среднее время: {sum(llm_times)/len(llm_times):.2f} сек")
    print(f"  Всего времени: {sum(llm_times):.2f} сек")
    print(f"  Среднее акторов: {sum(llm_counts)/len(llm_counts):.1f}")
    
    if hybrid_times:
        print(f"\nHybrid:")
        print(f"  Среднее время: {sum(hybrid_times)/len(hybrid_times):.2f} сек")
        print(f"  Всего времени: {sum(hybrid_times):.2f} сек")
        print(f"  Среднее акторов: {sum(hybrid_counts)/len(hybrid_counts):.1f}")
        
        avg_speedup = (sum(llm_times) / sum(hybrid_times)) if sum(hybrid_times) > 0 else 1
        print(f"\nОбщее ускорение: {avg_speedup:.2f}x")
    
    print("=" * 80 + "\n")


if __name__ == "__main__":
    # Можно запустить напрямую
    pytest.main([__file__, "-v", "-s"])

