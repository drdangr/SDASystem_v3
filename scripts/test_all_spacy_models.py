#!/usr/bin/env python3
"""
Скрипт для тестирования всех установленных моделей spaCy.
Показывает результаты NER для разных языков и моделей.
"""
import spacy
import sys
from typing import List, Tuple


def test_model(model_name: str, texts: List[Tuple[str, str]]) -> None:
    """
    Протестировать модель на разных текстах.
    
    Args:
        model_name: Название модели
        texts: Список кортежей (описание, текст)
    """
    try:
        print(f"\n{'='*80}")
        print(f"МОДЕЛЬ: {model_name}")
        print('='*80)
        
        nlp = spacy.load(model_name)
        print(f"✅ Модель загружена")
        print(f"   Компоненты: {', '.join(nlp.pipe_names)}")
        
        if 'ner' not in nlp.pipe_names:
            print("   ⚠️  NER компонент отсутствует!")
            return
        
        for desc, text in texts:
            print(f"\n{'-'*80}")
            print(f"Текст ({desc}):")
            print(f"  {text}")
            print(f"\nНайдено сущностей:")
            
            doc = nlp(text)
            entities = list(doc.ents)
            
            if entities:
                for ent in entities:
                    print(f"  - {ent.text:30} → {ent.label_}")
            else:
                print("  (сущности не найдены)")
            
    except OSError as e:
        print(f"❌ Модель {model_name} не найдена: {e}")
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")


def main():
    """Основная функция"""
    print("="*80)
    print("ТЕСТИРОВАНИЕ ВСЕХ УСТАНОВЛЕННЫХ МОДЕЛЕЙ SPACY")
    print("="*80)
    
    # Английские тексты
    english_texts = [
        ("Политика", "Vladimir Putin criticized NATO's decision. The United States announced new sanctions."),
        ("Технологии", "Tesla announced plans in Texas, US. Microsoft and Google responded to the news."),
        ("Смешанный", "Joe Biden met with Xi Jinping in China. The European Union supported the initiative.")
    ]
    
    # Русские тексты
    russian_texts = [
        ("Политика", "Владимир Путин раскритиковал решение НАТО. Соединенные Штаты объявили о новых санкциях."),
        ("Технологии", "Tesla объявила о планах в Техасе, США. Microsoft и Google отреагировали на новость."),
        ("Смешанный", "Джо Байден встретился с Си Цзиньпином в Китае. Европейский союз поддержал инициативу.")
    ]
    
    # Тестировать английские модели
    test_model("en_core_web_sm", english_texts)
    test_model("en_core_web_lg", english_texts)
    
    # Тестировать русские модели
    test_model("ru_core_news_sm", russian_texts)
    test_model("ru_core_news_md", russian_texts)
    
    print("\n" + "="*80)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*80)


if __name__ == "__main__":
    main()

