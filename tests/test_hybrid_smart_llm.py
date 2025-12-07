"""
Тест умного гибридного подхода: spaCy первично, LLM для перепроверки низкоконфиденциальных сущностей.
"""
import os
import json
from pathlib import Path

import pytest

from backend.services.llm_service import LLMService
from backend.services.ner_spacy_service import HybridNERService
from backend.models.entities import Actor, ActorType


def load_actors():
    """Загрузить акторов"""
    actors_file = Path(__file__).parent.parent / "data" / "actors.json"
    if not actors_file.exists():
        return []
    
    with open(actors_file, "r", encoding="utf-8") as f:
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
    service = HybridNERService(llm_service, use_spacy=True, spacy_model="en_core_web_sm")
    if actors:
        service.load_gazetteer(actors)
    return service


def test_smart_hybrid_low_confidence_verification(hybrid_service):
    """
    Тест: проверка что LLM используется для перепроверки низкоконфиденциальных сущностей.
    """
    # Текст с потенциально неоднозначными сущностями
    text = """John Smith visited the new office in downtown. 
    The company announced plans. Mr. Johnson commented on the situation."""
    
    print("\n" + "="*80)
    print("ТЕСТ: УМНАЯ ПЕРЕПРОВЕРКА НИЗКОКОНФИДЕНЦИАЛЬНЫХ СУЩНОСТЕЙ")
    print("="*80)
    print(f"\nТекст: {text}\n")
    
    # Тест 1: С перепроверкой низкого confidence
    print("-"*80)
    print("1. С перепроверкой низкого confidence (use_llm_for_low_confidence=True)")
    print("-"*80)
    results_with_check = hybrid_service.extract_actors(
        text,
        use_llm=True,
        use_llm_for_low_confidence=True,
        low_confidence_threshold=0.75
    )
    print(f"Найдено акторов: {len(results_with_check)}")
    for actor in results_with_check:
        conf = actor.get('confidence', 0)
        marker = "⚠️" if conf < 0.75 else "✅"
        print(f"  {marker} {actor.get('name'):20} ({actor.get('type'):12}) confidence: {conf:.2f}")
    
    # Тест 2: Без перепроверки
    print("\n" + "-"*80)
    print("2. Без перепроверки низкого confidence (use_llm_for_low_confidence=False)")
    print("-"*80)
    results_without_check = hybrid_service.extract_actors(
        text,
        use_llm=True,
        use_llm_for_low_confidence=False,
        low_confidence_threshold=0.75
    )
    print(f"Найдено акторов: {len(results_without_check)}")
    for actor in results_without_check:
        conf = actor.get('confidence', 0)
        marker = "⚠️" if conf < 0.75 else "✅"
        print(f"  {marker} {actor.get('name'):20} ({actor.get('type'):12}) confidence: {conf:.2f}")
    
    print("\n" + "="*80)
    print("ВЫВОД:")
    print("="*80)
    print(f"С перепроверкой: {len(results_with_check)} акторов")
    print(f"Без перепроверки: {len(results_without_check)} акторов")
    print("(LLM должен помочь подтвердить или дополнить результаты)")
    print("="*80 + "\n")


def test_smart_hybrid_few_results_llm_boost(hybrid_service):
    """
    Тест: если spaCy нашел мало результатов, LLM должен дополнить.
    """
    # Текст где spaCy может найти мало
    text = "The meeting discussed various topics."
    
    print("\n" + "="*80)
    print("ТЕСТ: ДОПОЛНЕНИЕ ПРИ МАЛОМ КОЛИЧЕСТВЕ РЕЗУЛЬТАТОВ")
    print("="*80)
    print(f"\nТекст: {text}\n")
    
    results = hybrid_service.extract_actors(text, use_llm=True)
    
    print(f"Найдено акторов: {len(results)}")
    print("(Если spaCy нашел мало (<3), LLM должен дополнить)")
    
    for actor in results:
        print(f"  - {actor.get('name')} ({actor.get('type')}, confidence: {actor.get('confidence', 0):.2f})")
    
    print("="*80 + "\n")


def test_tesla_news_smart_hybrid(hybrid_service):
    """
    Тест на реальной новости про Tesla с умным гибридным подходом.
    """
    text = """Tesla Opens New Gigafactory in Texas
Tesla announced the official opening of its latest Gigafactory in Austin, Texas, expanding US electric vehicle production capacity.
Tesla CEO Elon Musk celebrated the grand opening of the company's newest Gigafactory in Austin, Texas. The facility will produce the Cybertruck and Model Y vehicles, significantly boosting Tesla's manufacturing capacity in the United States. The $1.1 billion investment is expected to create thousands of jobs in the region."""
    
    print("\n" + "="*80)
    print("ТЕСТ: НОВОСТЬ ПРО TESLA С УМНЫМ ГИБРИДНЫМ ПОДХОДОМ")
    print("="*80)
    print(f"\nТекст: {text[:200]}...\n")
    
    results = hybrid_service.extract_actors(
        text,
        use_llm=True,
        use_llm_for_low_confidence=True,
        low_confidence_threshold=0.75
    )
    
    print(f"Найдено акторов: {len(results)}")
    print()
    print("Акторы (отсортированы по confidence):")
    
    # Сортируем по confidence
    sorted_results = sorted(results, key=lambda x: x.get('confidence', 0), reverse=True)
    
    for actor in sorted_results:
        conf = actor.get('confidence', 0)
        marker = "✅" if conf >= 0.75 else "⚠️"
        print(f"  {marker} {actor.get('name'):25} ({actor.get('type'):12}) confidence: {conf:.2f}")
    
    print()
    print("Ожидаемые акторы:")
    print("  - Tesla (company)")
    print("  - Elon Musk (person)")
    print("  - United States (country)")
    print("  - Austin, Texas (locations)")
    
    print("\n" + "="*80 + "\n")

