# Руководство по spaCy моделям

## Установленные модели
В проекте используются следующие модели spaCy для обработки естественного языка:

| Язык | Модель | Размер | Описание | Применение |
|---|---|---|---|---|
| Английский | `en_core_web_sm` | ~13 MB | Малая модель, быстрая | NER, определение фраз |
| Английский | `en_core_web_lg` | ~560 MB | Большая модель, точная | Сложный NER, векторы |
| Русский | `ru_core_news_md` | ~82 MB | Средняя модель | NER, лемматизация (Им. падеж) |

## Автоматический выбор (Dynamic Loading)

В `HybridNERService` реализована логика автоматического выбора модели в зависимости от языка текста:

```python
# backend/services/ner_spacy_service.py

def detect_language(text: str) -> str:
    """Определяет язык по наличию кириллицы"""
    # ...

def get_model_for_language(language: str) -> str:
    if language == 'ru':
        return 'ru_core_news_md'
    return 'en_core_web_sm' # Fallback
```

## Установка

Для развертывания проекта выполните:

```bash
# Установка всех необходимых моделей
python -m spacy download en_core_web_sm
python -m spacy download ru_core_news_md
```

## Лемматизация (Canonicalization)

Для русского языка используется `ru_core_news_md`, так как она содержит морфологический анализатор, необходимый для приведения имен в именительный падеж (например, "Путиным" -> "Путин").

