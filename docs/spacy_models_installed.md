# Установленные модели spaCy

## Статус установки

### ✅ Установленные модели

1. **en_core_web_sm** (3.7.1) - Малая английская модель
   - Размер: ~13 MB
   - Компоненты: tok2vec, tagger, parser, attribute_ruler, lemmatizer, ner
   - Рекомендуется для: быстрая обработка английских текстов

2. **en_core_web_lg** (3.7.1) - Большая английская модель
   - Размер: ~560 MB
   - Компоненты: tok2vec, tagger, parser, attribute_ruler, lemmatizer, ner
   - Рекомендуется для: максимальная точность для английских текстов
   - Word vectors включены

3. **ru_core_news_sm** (3.7.0) - Малая русская модель
   - Размер: ~42 MB
   - Компоненты: tok2vec, morphologizer, parser, attribute_ruler, lemmatizer, ner
   - Рекомендуется для: быстрая обработка русских текстов

4. **ru_core_news_md** (3.7.0) - Средняя русская модель
   - Размер: ~82 MB
   - Компоненты: tok2vec, morphologizer, parser, attribute_ruler, lemmatizer, ner
   - Рекомендуется для: баланс скорости и точности для русских текстов
   - Word vectors включены

## Использование в коде

### Автоматический выбор модели

```python
from backend.services.ner_spacy_service import HybridNERService

# Для английских текстов - большая модель (максимальная точность)
hybrid_en = HybridNERService(llm_service, spacy_model='en_core_web_lg')

# Для русских текстов - средняя модель (баланс скорости/точности)
hybrid_ru = HybridNERService(llm_service, spacy_model='ru_core_news_md')

# Для быстрой обработки - малые модели
hybrid_fast = HybridNERService(llm_service, spacy_model='en_core_web_sm')
```

### Определение языка текста

Можно добавить автоматическое определение языка и выбор модели:

```python
import spacy
from langdetect import detect

def get_model_for_text(text: str) -> str:
    """Определить язык и вернуть подходящую модель"""
    try:
        lang = detect(text)
        if lang == 'ru':
            return 'ru_core_news_md'  # Средняя русская
        elif lang == 'en':
            return 'en_core_web_lg'  # Большая английская
        else:
            return 'en_core_web_sm'  # Fallback на английскую малую
    except:
        return 'en_core_web_sm'  # Fallback
```

## Сравнение моделей

| Модель | Размер | Скорость | Точность | Word Vectors |
|--------|--------|----------|----------|--------------|
| en_core_web_sm | 13 MB | ⚡⚡⚡ Быстро | ⭐⭐ Хорошо | ❌ Нет |
| en_core_web_lg | 560 MB | ⚡ Средне | ⭐⭐⭐ Отлично | ✅ Да |
| ru_core_news_sm | 42 MB | ⚡⚡ Быстро | ⭐⭐ Хорошо | ❌ Нет |
| ru_core_news_md | 82 MB | ⚡⚡ Средне | ⭐⭐⭐ Отлично | ✅ Да |

## Рекомендации

### Для английских текстов:
- **Малая модель (sm)**: Быстрая обработка больших объемов
- **Большая модель (lg)**: Максимальная точность, когда важна канонизация

### Для русских текстов:
- **Малая модель (sm)**: Быстрая обработка
- **Средняя модель (md)**: Рекомендуется для большинства случаев (лучший баланс)

### Для продакшена:
- Используйте большие модели (lg/md) для максимальной точности
- Или малые модели (sm) для высокой производительности

## Проверка установки

```bash
# Проверить все установленные модели
python -m spacy validate

# Тест конкретной модели
python -c "import spacy; nlp = spacy.load('en_core_web_lg'); print('✅ Модель работает')"
```

## Установка других моделей (если нужно)

### Другие языки:
- Немецкий: `de_core_news_sm`
- Французский: `fr_core_news_sm`
- Испанский: `es_core_news_sm`
- Китайский: `zh_core_web_sm`

См. все доступные модели: https://github.com/explosion/spacy-models/releases

### Установка через pip:
```bash
pip install https://github.com/explosion/spacy-models/releases/download/{model}-{version}/{model}-{version}-py3-none-any.whl
```

## Интеграция в проект

Модели автоматически используются в:
- `HybridNERService` - гибридный NER сервис
- `NERSpacyService` - базовый spaCy сервис
- API endpoint `/api/news/{news_id}/actors/refresh` (через HybridNERService)

По умолчанию используется `en_core_web_sm`, но можно настроить через переменные окружения или параметры конструктора.

