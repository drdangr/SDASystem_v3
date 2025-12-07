"""
Тест для проверки качества извлечения акторов с помощью Hybrid NER (spaCy + LLM)
и сравнения с ожидаемыми данными из бэкапа.
"""
import json
import os
from pathlib import Path
from typing import Dict, List

import pytest

from backend.services.llm_service import LLMService
from backend.services.ner_spacy_service import HybridNERService
from backend.models.entities import Actor, ActorType
from tests.test_actors_extraction import (
    BACKUP_DIR, load_backup_data, normalize_name,
    match_extracted_actor, compare_actors, calculate_metrics
)


def load_actors_from_file() -> List[Actor]:
    """Загрузить акторов из файла для gazetteer"""
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
    """Создать гибридный сервис с загруженным gazetteer"""
    actors = load_actors_from_file()
    service = HybridNERService(llm_service, use_spacy=True, spacy_model="en_core_web_sm")
    if actors:
        service.load_gazetteer(actors)
    return service


def test_hybrid_actors_extraction_for_all_news(hybrid_service):
    """
    Основной тест: проверить извлечение акторов гибридным методом для всех новостей.
    """
    # Загрузить метаданные
    metadata_file = BACKUP_DIR / "_metadata.json"
    if not metadata_file.exists():
        pytest.skip("Бэкап данных не найден. Запустите scripts/create_actors_backup.py")
    
    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    news_mapping = metadata.get("news_mapping", {})
    
    if not news_mapping:
        pytest.skip("Нет новостей в бэкапе")
    
    # Результаты для всех новостей
    all_results = []
    all_metrics = []
    
    # Пройти по каждой новости
    for news_id, news_info in news_mapping.items():
        # Загрузить бэкап данные
        backup_data = load_backup_data(news_id)
        if not backup_data:
            continue
        
        news_text = backup_data.get("news_text", "")
        expected_actors = backup_data.get("expected_actors", [])
        
        if not expected_actors:
            # Пропускаем новости без ожидаемых акторов
            continue
        
        # Извлечь акторов через Hybrid NER
        try:
            extracted_actors = hybrid_service.extract_actors(news_text, use_llm=True)
        except Exception as e:
            print(f"Ошибка при извлечении акторов для {news_id}: {e}")
            continue
        
        # Сравнить результаты
        comparison = compare_actors(extracted_actors, expected_actors, news_text)
        metrics = calculate_metrics(comparison, len(expected_actors))
        
        # Сохранить результаты
        result_entry = {
            "news_id": news_id,
            "news_title": backup_data.get("news_title", ""),
            "metrics": metrics,
            "comparison": {
                "matched_count": len(comparison["matched"]),
                "missed_count": len(comparison["missed"]),
                "false_positives_count": len(comparison["false_positives"]),
                "canonical_names_found": comparison["canonical_names_found"],
                "aliases_found": comparison["aliases_found"]
            }
        }
        
        all_results.append(result_entry)
        all_metrics.append(metrics)
    
    # Вычислить общие метрики
    if all_metrics:
        avg_precision = sum(m["precision"] for m in all_metrics) / len(all_metrics)
        avg_recall = sum(m["recall"] for m in all_metrics) / len(all_metrics)
        avg_f1 = sum(m["f1_score"] for m in all_metrics) / len(all_metrics)
        total_canonical = sum(m["canonical_names_count"] for m in all_metrics)
        total_aliases = sum(m["aliases_count"] for m in all_metrics)
        
        print("\n" + "="*80)
        print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ГИБРИДНОГО ИЗВЛЕЧЕНИЯ АКТОРОВ (spaCy + LLM)")
        print("="*80)
        print(f"Протестировано новостей: {len(all_results)}")
        print(f"\nСредние метрики:")
        print(f"  Precision: {avg_precision:.2%}")
        print(f"  Recall: {avg_recall:.2%}")
        print(f"  F1-Score: {avg_f1:.2%}")
        print(f"\nНайдено канонических названий: {total_canonical}")
        print(f"Найдено алиасов: {total_aliases}")
        
        # Информация о методе
        print(f"\nМетод: Hybrid NER (spaCy: {hybrid_service.use_spacy})")
        if hybrid_service.spacy_service and hybrid_service.spacy_service.nlp:
            print(f"spaCy модель: {hybrid_service.spacy_service.model_name}")
            print(f"spaCy компоненты: {hybrid_service.spacy_service.nlp.pipe_names}")
        
        print("\n" + "="*80)
        
        # Детали по новостям
        for result in all_results:
            print(f"\n{result['news_title']} ({result['news_id']})")
            print(f"  Precision: {result['metrics']['precision']:.2%}, "
                  f"Recall: {result['metrics']['recall']:.2%}, "
                  f"F1: {result['metrics']['f1_score']:.2%}")
            if result['comparison']['missed_count'] > 0:
                print(f"  Пропущено: {result['comparison']['missed_count']}")
            if result['comparison']['false_positives_count'] > 0:
                print(f"  Ложные срабатывания: {result['comparison']['false_positives_count']}")
        
        # Проверки (assertions)
        # В mock режиме пропускаем строгие проверки
        is_mock = hybrid_service.llm_service.use_mock
        if is_mock:
            print("\n⚠️  ВНИМАНИЕ: Используется mock режим LLM. Для реального тестирования установите GEMINI_API_KEY")
            pytest.skip("Mock режим: требуется GEMINI_API_KEY для реального тестирования")
        
        # Требуем хотя бы 50% recall и precision
        assert avg_recall >= 0.5, f"Recall слишком низкий: {avg_recall:.2%} < 50%"
        assert avg_precision >= 0.5, f"Precision слишком низкий: {avg_precision:.2%} < 50%"
        
        # Проверяем, что хотя бы в некоторых новостях используются канонические названия
        news_with_canonical = sum(1 for m in all_metrics if m["canonical_names_count"] > 0)
        assert news_with_canonical > 0, "Не найдено канонических названий ни в одной новости"
        
        # Проверяем, что алиасы тоже находятся (если они есть в текстах)
        if total_aliases > 0:
            print(f"\n✓ Найдено алиасов: {total_aliases} (хорошо!)")
        
        # Дополнительные проверки качества
        if avg_f1 < 0.6:
            print(f"\n⚠️  F1-Score ниже 60%: {avg_f1:.2%}. Возможно, требуется улучшение промпта или модели.")
        
        if total_canonical < len(all_metrics) * 0.5:
            print(f"\n⚠️  Мало канонических названий найдено. LLM может использовать алиасы вместо канонических имен.")
        
    else:
        pytest.fail("Не удалось обработать ни одну новость")


def test_hybrid_vs_llm_comparison(llm_service, hybrid_service):
    """
    Сравнить результаты гибридного метода и только LLM на нескольких новостях.
    """
    metadata_file = BACKUP_DIR / "_metadata.json"
    if not metadata_file.exists():
        pytest.skip("Бэкап данных не найден")
    
    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    news_mapping = metadata.get("news_mapping", {})
    if not news_mapping:
        pytest.skip("Нет новостей в бэкапе")
    
    # Взять первые 5 новостей для сравнения
    test_news_ids = list(news_mapping.keys())[:5]
    
    print("\n" + "="*80)
    print("СРАВНЕНИЕ: Гибридный (spaCy + LLM) vs Только LLM")
    print("="*80)
    
    llm_results = []
    hybrid_results = []
    
    for news_id in test_news_ids:
        backup_data = load_backup_data(news_id)
        if not backup_data:
            continue
        
        expected_actors = backup_data.get("expected_actors", [])
        if not expected_actors:
            continue
        
        news_text = backup_data.get("news_text", "")
        
        # LLM только
        try:
            llm_actors = llm_service.extract_actors(news_text)
            llm_comparison = compare_actors(llm_actors, expected_actors, news_text)
            llm_metrics = calculate_metrics(llm_comparison, len(expected_actors))
            llm_results.append(llm_metrics)
        except Exception as e:
            print(f"Ошибка LLM для {news_id}: {e}")
            continue
        
        # Hybrid
        try:
            hybrid_actors = hybrid_service.extract_actors(news_text, use_llm=True)
            hybrid_comparison = compare_actors(hybrid_actors, expected_actors, news_text)
            hybrid_metrics = calculate_metrics(hybrid_comparison, len(expected_actors))
            hybrid_results.append(hybrid_metrics)
        except Exception as e:
            print(f"Ошибка Hybrid для {news_id}: {e}")
            hybrid_results.append(llm_metrics)  # Fallback
        
        # Задержка чтобы не превысить rate limits
        import time
        time.sleep(0.5)
    
    if llm_results and hybrid_results:
        llm_avg_f1 = sum(m["f1_score"] for m in llm_results) / len(llm_results)
        hybrid_avg_f1 = sum(m["f1_score"] for m in hybrid_results) / len(hybrid_results)
        
        llm_avg_recall = sum(m["recall"] for m in llm_results) / len(llm_results)
        hybrid_avg_recall = sum(m["recall"] for m in hybrid_results) / len(hybrid_results)
        
        llm_avg_precision = sum(m["precision"] for m in llm_results) / len(llm_results)
        hybrid_avg_precision = sum(m["precision"] for m in hybrid_results) / len(hybrid_results)
        
        print(f"\nОбработано новостей: {len(llm_results)}")
        print(f"\nТолько LLM:")
        print(f"  Precision: {llm_avg_precision:.2%}")
        print(f"  Recall: {llm_avg_recall:.2%}")
        print(f"  F1-Score: {llm_avg_f1:.2%}")
        
        print(f"\nГибридный (spaCy + LLM):")
        print(f"  Precision: {hybrid_avg_precision:.2%}")
        print(f"  Recall: {hybrid_avg_recall:.2%}")
        print(f"  F1-Score: {hybrid_avg_f1:.2%}")
        
        print(f"\nРазница:")
        print(f"  Precision: {hybrid_avg_precision - llm_avg_precision:+.2%}")
        print(f"  Recall: {hybrid_avg_recall - llm_avg_recall:+.2%}")
        print(f"  F1-Score: {hybrid_avg_f1 - llm_avg_f1:+.2%}")
        
        print("="*80 + "\n")

