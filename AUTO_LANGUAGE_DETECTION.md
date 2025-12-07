# Автоматическое определение языка и выбор модели spaCy

## Обзор

Система теперь автоматически определяет язык текста и выбирает соответствующую модель spaCy для извлечения акторов.

## Как это работает

1. **Определение языка**: При обработке текста система проверяет наличие кириллических символов
   - Если обнаружена кириллица (>30% от всех букв) → русский язык
   - Иначе → английский язык

2. **Выбор модели**:
   - **Русский текст** → `ru_core_news_md` (или `ru_core_news_lg` если `prefer_large_models=True`)
   - **Английский текст** → `en_core_web_sm` (или `en_core_web_lg` если `prefer_large_models=True`)

3. **Кэширование моделей**: Загруженные модели кэшируются для быстрого переключения между языками

4. **Fallback**: Если нужная модель недоступна, система пробует альтернативные модели того же языка

## Преимущества

- ✅ Автоматическая обработка смешанных языков
- ✅ Оптимальная модель для каждого языка
- ✅ Не нужно вручную указывать язык
- ✅ Работает "из коробки" без дополнительной настройки

## Использование

### По умолчанию (автоматическое определение)

```python
from backend.services.ner_spacy_service import create_hybrid_ner_service

# Автоматически определяет язык и выбирает модель
service = create_hybrid_ner_service(
    llm_service,
    use_spacy=True,
    auto_detect_language=True  # По умолчанию True
)
```

### С явным указанием модели (отключает автоопределение)

```python
# Использовать конкретную модель для всех текстов
service = create_hybrid_ner_service(
    llm_service,
    use_spacy=True,
    spacy_model="ru_core_news_lg",
    auto_detect_language=False
)
```

### Предпочитать большие модели

```python
# Использовать большие модели (lg) вместо средних (md)
service = create_hybrid_ner_service(
    llm_service,
    use_spacy=True,
    prefer_large_models=True  # ru_core_news_lg вместо ru_core_news_md
)
```

## Установка моделей

Для работы с русским языком рекомендуется установить русские модели:

```bash
# Установить все недостающие модели
python3 scripts/install_spacy_models.py

# Или вручную:
python -m spacy download ru_core_news_sm
python -m spacy download ru_core_news_md
python -m spacy download ru_core_news_lg
```

## Примеры работы

### Русский текст
```python
text = "Владимир Путин раскритиковал решение НАТО. Соединенные Штаты объявили о новых санкциях."
# Автоматически использует ru_core_news_md
actors = service.extract_actors(text)
```

### Английский текст
```python
text = "Vladimir Putin criticized NATO's decision. The United States announced new sanctions."
# Автоматически использует en_core_web_sm
actors = service.extract_actors(text)
```

### Смешанный текст
```python
text = "Vladimir Putin раскритиковал NATO. The United States объявили о санкциях."
# Определяет язык по преобладающему (кириллица >30% → русский)
# Использует ru_core_news_md
actors = service.extract_actors(text)
```

## Настройка в системе

В `backend/api/routes.py` система автоматически использует автоопределение:

```python
actors_extraction_service = ActorsExtractionService(
    graph_manager,
    default_llm_service,
    data_dir="data",
    use_spacy=True,
    spacy_model=os.getenv("SPACY_MODEL", "en_core_web_sm"),  # Используется только если не None
)
```

Если `SPACY_MODEL` не установлен или равен `"en_core_web_sm"`, система использует автоматическое определение.

## Логирование

Система логирует выбор модели:

```
INFO: Загружена модель spaCy: ru_core_news_md
INFO: Используется альтернативная модель: ru_core_news_sm
```

## Производительность

- **Кэширование**: Модели загружаются один раз и кэшируются
- **Быстрое переключение**: Переключение между языками происходит мгновенно
- **Память**: Одновременно могут быть загружены несколько моделей (обычно 2-3)

## Обратная совместимость

Старый код продолжает работать:
- Если указана конкретная модель → используется она
- Если модель не указана → используется автоопределение
- Можно отключить автоопределение через `auto_detect_language=False`

