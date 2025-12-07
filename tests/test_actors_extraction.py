"""
Тест для проверки качества извлечения акторов с помощью LLM-сервиса.

Тест проходит по всем новостям, извлекает акторов через LLMService.extract_actors
и сравнивает результаты с ожидаемыми данными из бэкапа.

Критерии проверки:
- Большое количество совпадений
- Использование канонических названий
- Выявление косвенных упоминаний (через алиасы)
- Заполнение алиасов (неканонических названий), если они есть в текстах
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict

import pytest

from backend.services.llm_service import LLMService


PROJECT_ROOT = Path(__file__).parent.parent
BACKUP_DIR = PROJECT_ROOT / "data" / "backup" / "actors_test"


def normalize_name(name: str) -> str:
    """Нормализовать имя для сравнения"""
    return name.lower().strip()


def load_backup_data(news_id: str) -> Dict:
    """Загрузить бэкап данные для новости"""
    backup_file = BACKUP_DIR / f"{news_id}.json"
    if not backup_file.exists():
        return None
    with open(backup_file, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_mentions_from_text(text: str, all_mentions: Set[str]) -> Set[str]:
    """
    Извлечь упоминания из текста на основе известных вариантов.
    Проверяет все возможные варианты упоминания (канонические имена и алиасы).
    """
    text_lower = text.lower()
    found_mentions = set()
    
    for mention in all_mentions:
        mention_normalized = normalize_name(mention)
        # Проверяем наличие упоминания в тексте (слово целиком)
        # Простая проверка на вхождение
        if mention_normalized in text_lower:
            found_mentions.add(mention)
        # Также проверяем части имени (для сложных имен типа "Ursula von der Leyen")
        words = mention_normalized.split()
        if len(words) > 1:
            # Если хотя бы часть имени найдена, считаем упоминание
            for word in words:
                if len(word) > 3 and word in text_lower:
                    found_mentions.add(mention)
                    break
    
    return found_mentions


def match_extracted_actor(extracted: Dict, expected_actors: List[Dict]) -> Tuple[Dict, float]:
    """
    Найти соответствие между извлеченным актором и ожидаемым.
    
    Returns:
        (matched_expected_actor, confidence_score)
        confidence_score: 1.0 - точное совпадение, 0.7 - совпадение по алиасу, 0.5 - частичное, 0.0 - не найдено
    """
    extracted_name = normalize_name(extracted.get("name", ""))
    if not extracted_name:
        return None, 0.0
    
    best_match = None
    best_score = 0.0
    
    # Словарь для быстрого маппинга алиасов -> канонических форм
    alias_to_canonical = {}
    for expected in expected_actors:
        canonical = normalize_name(expected.get("canonical_name", ""))
        for alias in expected.get("aliases", []):
            alias_normalized = normalize_name(alias)
            alias_to_canonical[alias_normalized] = expected
        # Также добавляем каноническое имя
        if canonical:
            alias_to_canonical[canonical] = expected
    
    # Проверка прямого совпадения
    if extracted_name in alias_to_canonical:
        expected = alias_to_canonical[extracted_name]
        canonical = normalize_name(expected.get("canonical_name", ""))
        # Если это каноническое имя - отлично
        if extracted_name == canonical:
            return expected, 1.0
        # Если это алиас - тоже хорошо
        return expected, 0.85
    
    # Проверка частичных совпадений
    for expected in expected_actors:
        canonical = normalize_name(expected.get("canonical_name", ""))
        
        # Точное совпадение канонического имени
        if extracted_name == canonical:
            return expected, 1.0
        
        # Проверка на включение (например, "United States" содержит "US")
        if canonical and len(canonical) > 3:
            # Если извлеченное имя - часть канонического или наоборот
            if extracted_name in canonical and len(extracted_name) >= 3:
                score = 0.9 if len(extracted_name) >= len(canonical) * 0.6 else 0.7
                if score > best_score:
                    best_match = expected
                    best_score = score
            elif canonical in extracted_name and len(canonical) >= 3:
                score = 0.85
                if score > best_score:
                    best_match = expected
                    best_score = score
        
        # Проверка алиасов
        aliases = expected.get("aliases", [])
        for alias in aliases:
            alias_normalized = normalize_name(alias)
            # Точное совпадение алиаса
            if extracted_name == alias_normalized:
                score = 0.85
                if score > best_score:
                    best_match = expected
                    best_score = score
            # Частичное совпадение алиаса
            elif alias_normalized and len(alias_normalized) > 2:
                if extracted_name in alias_normalized:
                    score = 0.75
                    if score > best_score:
                        best_match = expected
                        best_score = score
                elif alias_normalized in extracted_name:
                    score = 0.8
                    if score > best_score:
                        best_match = expected
                        best_score = score
        
        # Проверка всех упоминаний из бэкапа
        all_mentions = expected.get("normalized_names", [])
        for mention in all_mentions:
            if extracted_name == mention:
                score = 0.8
                if score > best_score:
                    best_match = expected
                    best_score = score
            elif mention and len(mention) > 3:
                # Частичное совпадение
                if extracted_name in mention or mention in extracted_name:
                    score = 0.7
                    if score > best_score:
                        best_match = expected
                        best_score = score
    
    return best_match, best_score


def compare_actors(
    extracted_actors: List[Dict],
    expected_actors: List[Dict],
    news_text: str
) -> Dict:
    """
    Сравнить извлеченных акторов с ожидаемыми.
    
    Returns словарь с метриками:
    - matched: список найденных ожидаемых акторов
    - missed: список пропущенных ожидаемых акторов
    - false_positives: список извлеченных, но не ожидаемых акторов
    - matches_by_type: разбивка совпадений по типам совпадений
    - aliases_found: список найденных алиасов
    """
    result = {
        "matched": [],
        "missed": [],
        "false_positives": [],
        "matches_by_type": defaultdict(int),
        "aliases_found": [],
        "canonical_names_found": [],
        "partial_matches": []
    }
    
    # Создать множество для отслеживания найденных ожидаемых акторов
    expected_found = set()
    
    # Для каждого извлеченного актора найти соответствие
    for extracted in extracted_actors:
        matched, score = match_extracted_actor(extracted, expected_actors)
        
        if matched:
            expected_id = matched.get("id")
            expected_found.add(expected_id)
            
            match_info = {
                "extracted": extracted,
                "expected": matched,
                "score": score
            }
            
            if score >= 1.0:
                result["matches_by_type"]["exact_canonical"] += 1
                result["canonical_names_found"].append({
                    "expected": matched.get("canonical_name"),
                    "extracted": extracted.get("name")
                })
            elif score >= 0.7:
                result["matches_by_type"]["alias_match"] += 1
                # Проверим, является ли извлеченное имя алиасом
                extracted_name = extracted.get("name", "")
                expected_aliases = matched.get("aliases", [])
                if any(normalize_name(alias) == normalize_name(extracted_name) for alias in expected_aliases):
                    result["aliases_found"].append({
                        "alias": extracted_name,
                        "canonical": matched.get("canonical_name")
                    })
            else:
                result["matches_by_type"]["partial_match"] += 1
                result["partial_matches"].append({
                    "extracted": extracted.get("name"),
                    "expected": matched.get("canonical_name"),
                    "score": score
                })
            
            result["matched"].append(match_info)
        else:
            # Ложное срабатывание - актор не ожидался
            result["false_positives"].append(extracted)
    
    # Найти пропущенные акторы
    for expected in expected_actors:
        expected_id = expected.get("id")
        if expected_id not in expected_found:
            # Проверим, есть ли упоминание в тексте
            all_mentions = set(expected.get("all_mentions", []))
            text_mentions = extract_mentions_from_text(news_text, all_mentions)
            
            result["missed"].append({
                "expected": expected,
                "mentioned_in_text": len(text_mentions) > 0,
                "text_mentions": list(text_mentions)
            })
    
    return result


def calculate_metrics(comparison_result: Dict, total_expected: int) -> Dict:
    """Вычислить метрики качества извлечения"""
    matched_count = len(comparison_result["matched"])
    missed_count = len(comparison_result["missed"])
    false_positives_count = len(comparison_result["false_positives"])
    
    precision = matched_count / (matched_count + false_positives_count) if (matched_count + false_positives_count) > 0 else 0.0
    recall = matched_count / total_expected if total_expected > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "matched_count": matched_count,
        "missed_count": missed_count,
        "false_positives_count": false_positives_count,
        "total_expected": total_expected,
        "canonical_names_count": len(comparison_result["canonical_names_found"]),
        "aliases_count": len(comparison_result["aliases_found"]),
        "partial_matches_count": len(comparison_result["partial_matches"])
    }


@pytest.fixture
def llm_service():
    """Создать LLM сервис (может использовать mock если нет API ключа)"""
    api_key = os.getenv("GEMINI_API_KEY")
    use_mock = os.getenv("LLM_FORCE_MOCK") == "1" or not api_key
    
    service = LLMService(
        api_key=api_key,
        use_mock=use_mock,
        temperature=0.3
    )
    return service


def test_actors_extraction_for_all_news(llm_service):
    """
    Основной тест: проверить извлечение акторов для всех новостей.
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
        
        # Извлечь акторов через LLM
        try:
            extracted_actors = llm_service.extract_actors(news_text)
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
        print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ИЗВЛЕЧЕНИЯ АКТОРОВ")
        print("="*80)
        print(f"Протестировано новостей: {len(all_results)}")
        print(f"\nСредние метрики:")
        print(f"  Precision: {avg_precision:.2%}")
        print(f"  Recall: {avg_recall:.2%}")
        print(f"  F1-Score: {avg_f1:.2%}")
        print(f"\nНайдено канонических названий: {total_canonical}")
        print(f"Найдено алиасов: {total_aliases}")
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
        is_mock = llm_service.use_mock
        if is_mock:
            print("\n⚠️  ВНИМАНИЕ: Используется mock режим LLM. Для реального тестирования установите GEMINI_API_KEY")
            print("   Тест пропущен - установите API ключ для проверки качества извлечения акторов")
            pytest.skip("Mock режим: требуется GEMINI_API_KEY для реального тестирования")
        
        # Требуем хотя бы 50% recall и precision (только в реальном режиме)
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


def test_single_news_detailed(llm_service):
    """
    Детальный тест для одной новости - для отладки.
    Можно запустить с параметром -k test_single_news_detailed для детального анализа.
    """
    metadata_file = BACKUP_DIR / "_metadata.json"
    if not metadata_file.exists():
        pytest.skip("Бэкап данных не найден")
    
    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    news_mapping = metadata.get("news_mapping", {})
    if not news_mapping:
        pytest.skip("Нет новостей в бэкапе")
    
    # Взять первую новость с акторами
    for news_id, news_info in news_mapping.items():
        backup_data = load_backup_data(news_id)
        if not backup_data:
            continue
        
        expected_actors = backup_data.get("expected_actors", [])
        if not expected_actors:
            continue
        
        news_text = backup_data.get("news_text", "")
        
        # Извлечь акторов
        extracted_actors = llm_service.extract_actors(news_text)
        
        # Детальное сравнение
        comparison = compare_actors(extracted_actors, expected_actors, news_text)
        
        print("\n" + "="*80)
        print(f"ДЕТАЛЬНЫЙ АНАЛИЗ: {backup_data.get('news_title')}")
        print("="*80)
        print(f"\nТекст новости:\n{news_text[:500]}...")
        
        print(f"\nОжидаемые акторы ({len(expected_actors)}):")
        for expected in expected_actors:
            print(f"  - {expected['canonical_name']} ({expected['actor_type']})")
            if expected.get('aliases'):
                print(f"    Алиасы: {', '.join(expected['aliases'])}")
        
        print(f"\nИзвлеченные акторы ({len(extracted_actors)}):")
        for extracted in extracted_actors:
            print(f"  - {extracted.get('name')} ({extracted.get('type')}, confidence: {extracted.get('confidence', 0):.2f})")
        
        print(f"\nСовпадения ({len(comparison['matched'])}):")
        for match in comparison['matched']:
            extracted = match['extracted']
            expected = match['expected']
            score = match['score']
            print(f"  ✓ {extracted.get('name')} -> {expected.get('canonical_name')} (score: {score:.2f})")
        
        if comparison['missed']:
            print(f"\nПропущено ({len(comparison['missed'])}):")
            for missed in comparison['missed']:
                expected = missed['expected']
                print(f"  ✗ {expected.get('canonical_name')} ({expected.get('actor_type')})")
                if missed.get('mentioned_in_text'):
                    print(f"    Упоминается в тексте как: {', '.join(missed.get('text_mentions', []))}")
        
        if comparison['false_positives']:
            print(f"\nЛожные срабатывания ({len(comparison['false_positives'])}):")
            for fp in comparison['false_positives']:
                print(f"  ? {fp.get('name')} ({fp.get('type')})")
        
        print("="*80 + "\n")
        
        # Останавливаемся на первой новости
        break

