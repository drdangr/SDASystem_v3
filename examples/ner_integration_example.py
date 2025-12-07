"""
Пример использования различных NER сервисов для извлечения акторов.

Демонстрирует:
1. Базовый NERService (pattern matching)
2. NERSpacyService (spaCy)
3. HybridNERService (spaCy + LLM)
4. Сравнение результатов
"""
import json
from pathlib import Path

# Добавляем корневую директорию в путь
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.ner_service import NERService
from backend.services.ner_spacy_service import NERSpacyService, HybridNERService
from backend.services.llm_service import LLMService
from backend.models.entities import Actor, ActorType


def load_actors_from_file(actors_file: str = "data/actors.json") -> list:
    """Загрузить акторов из JSON файла"""
    actors_path = Path(__file__).parent.parent / actors_file
    if not actors_path.exists():
        print(f"Файл {actors_file} не найден")
        return []
    
    with open(actors_path, "r", encoding="utf-8") as f:
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


def compare_ner_methods(text: str):
    """Сравнить различные методы извлечения акторов"""
    print("=" * 80)
    print("СРАВНЕНИЕ МЕТОДОВ ИЗВЛЕЧЕНИЯ АКТОРОВ")
    print("=" * 80)
    print(f"\nТекст для анализа:\n{text}\n")
    
    # Загрузить акторов
    actors = load_actors_from_file()
    print(f"Загружено {len(actors)} акторов в gazetteer\n")
    
    # Метод 1: Базовый NERService (pattern matching)
    print("-" * 80)
    print("1. Базовый NERService (pattern matching)")
    print("-" * 80)
    basic_ner = NERService()
    basic_ner.load_gazetteer(actors)
    known_ids_basic, new_actors_basic = basic_ner.extract_actors_from_text(text)
    print(f"Найдено известных акторов: {len(known_ids_basic)}")
    for actor_id in known_ids_basic:
        actor = basic_ner.gazetteer.get(actor_id)
        if actor:
            print(f"  - {actor.canonical_name} ({actor.actor_type.value})")
    print(f"Найдено новых акторов: {len(new_actors_basic)}")
    for actor in new_actors_basic[:5]:  # Показать первые 5
        print(f"  - {actor.canonical_name} ({actor.actor_type.value})")
    
    # Метод 2: spaCy NER (если доступно)
    print("\n" + "-" * 80)
    print("2. NERSpacyService (spaCy)")
    print("-" * 80)
    try:
        spacy_ner = NERSpacyService(model_name="xx_ent_wiki_sm")  # Многоязычная модель
        if spacy_ner.nlp:
            spacy_ner.load_gazetteer(actors)
            known_ids_spacy, new_actors_spacy = spacy_ner.extract_actors_from_text(text)
            print(f"Найдено известных акторов: {len(known_ids_spacy)}")
            for actor_id in known_ids_spacy:
                actor = spacy_ner.gazetteer.get(actor_id)
                if actor:
                    print(f"  - {actor.canonical_name} ({actor.actor_type.value})")
            print(f"Найдено новых акторов: {len(new_actors_spacy)}")
            for actor in new_actors_spacy[:5]:
                print(f"  - {actor.canonical_name} ({actor.actor_type.value}, confidence: {actor.metadata.get('confidence', 0.7):.2f})")
            
            # Извлечение с каноническими именами
            canonical_results = spacy_ner.extract_with_canonical_names(text)
            print(f"\nИзвлечение с каноническими именами: {len(canonical_results)}")
            for result in canonical_results[:5]:
                print(f"  - {result['name']} ({result['type']}, confidence: {result['confidence']:.2f})")
        else:
            print("spaCy модель не загружена. Установите: python -m spacy download xx_ent_wiki_sm")
    except Exception as e:
        print(f"Ошибка при использовании spaCy: {e}")
    
    # Метод 3: LLM (Gemini)
    print("\n" + "-" * 80)
    print("3. LLM Service (Gemini)")
    print("-" * 80)
    try:
        import os
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            llm_service = LLMService(api_key=api_key, use_mock=False)
            llm_actors = llm_service.extract_actors(text)
            print(f"Найдено акторов: {len(llm_actors)}")
            for actor in llm_actors[:5]:
                print(f"  - {actor['name']} ({actor['type']}, confidence: {actor.get('confidence', 0.7):.2f})")
        else:
            print("GEMINI_API_KEY не установлен. Используется mock режим.")
            llm_service = LLMService(use_mock=True)
            llm_actors = llm_service.extract_actors(text)
            print(f"Найдено акторов (mock): {len(llm_actors)}")
    except Exception as e:
        print(f"Ошибка при использовании LLM: {e}")
    
    # Метод 4: Гибридный (spaCy + LLM)
    print("\n" + "-" * 80)
    print("4. HybridNERService (spaCy + LLM)")
    print("-" * 80)
    try:
        llm_service = LLMService(api_key=os.getenv("GEMINI_API_KEY"), use_mock=not bool(os.getenv("GEMINI_API_KEY")))
        hybrid_ner = HybridNERService(llm_service, use_spacy=True)
        hybrid_ner.load_gazetteer(actors)
        hybrid_actors = hybrid_ner.extract_actors(text, use_llm=True)
        print(f"Найдено акторов: {len(hybrid_actors)}")
        for actor in hybrid_actors[:5]:
            print(f"  - {actor['name']} ({actor['type']}, confidence: {actor.get('confidence', 0.7):.2f})")
    except Exception as e:
        print(f"Ошибка при использовании гибридного сервиса: {e}")
    
    print("\n" + "=" * 80)
    print("Сравнение завершено")
    print("=" * 80)


if __name__ == "__main__":
    # Пример текста для анализа
    sample_text = """
    Vladimir Putin criticized NATO's decision to increase military support to Ukraine. 
    The United States announced new sanctions. Tesla CEO Elon Musk commented on the situation. 
    The European Union is considering additional measures.
    """
    
    compare_ner_methods(sample_text)

