# Руководство по интеграции NER сервисов

## Быстрый старт

### 1. Установка spaCy

```bash
# Установка библиотеки
pip install spacy

# Установка русской модели (рекомендуется)
python -m spacy download ru_core_news_lg

# Или многоязычная модель (для английского и других языков)
python -m spacy download xx_ent_wiki_sm

# Для английского
python -m spacy download en_core_web_lg
```

### 2. Базовое использование

```python
from backend.services.ner_spacy_service import NERSpacyService
from backend.models.entities import Actor

# Инициализация
service = NERSpacyService(model_name="ru_core_news_lg")

# Загрузка известных акторов
actors = load_actors_from_json("data/actors.json")
service.load_gazetteer(actors)

# Извлечение акторов
text = "Vladimir Putin criticized the United States."
known_ids, new_actors = service.extract_actors_from_text(text)

# Результат
print(f"Найдено {len(known_ids)} известных акторов")
print(f"Найдено {len(new_actors)} новых акторов")
```

### 3. Гибридный подход (spaCy + LLM)

```python
from backend.services.ner_spacy_service import HybridNERService
from backend.services.llm_service import LLMService

# Создание гибридного сервиса
llm_service = LLMService(api_key=os.getenv("GEMINI_API_KEY"))
hybrid_service = HybridNERService(llm_service, use_spacy=True)

# Загрузка gazetteer
hybrid_service.load_gazetteer(actors)

# Извлечение (spaCy делает первичное извлечение, LLM улучшает)
results = hybrid_service.extract_actors(text, use_llm=True)
```

## Стратегии использования

### Стратегия 1: Только spaCy (быстро, дешево)

**Когда использовать**:
- Нужна быстрая обработка больших объемов текста
- Ограниченный бюджет на API
- Базовое извлечение сущностей достаточно

**Код**:
```python
service = NERSpacyService(model_name="ru_core_news_lg")
service.load_gazetteer(actors)
known_ids, new_actors = service.extract_actors_from_text(text)
```

**Производительность**: ~1000 текстов/сек  
**Точность**: ~70-80% F1  
**Стоимость**: $0 (локальная обработка)

---

### Стратегия 2: Только LLM (точность)

**Когда использовать**:
- Нужна максимальная точность
- Важна канонизация имен
- Небольшие объемы текста

**Код**:
```python
llm_service = LLMService(api_key=api_key)
actors = llm_service.extract_actors(text)
```

**Производительность**: ~10-50 текстов/сек (зависит от API)  
**Точность**: ~89% F1 (по нашим тестам)  
**Стоимость**: ~$0.001-0.01 за 1000 текстов

---

### Стратегия 3: Гибридный (рекомендуется)

**Когда использовать**:
- Нужен баланс скорости, точности и стоимости
- Обработка смешанных текстов (русский + английский)
- Продакшн окружение

**Код**:
```python
hybrid_service = HybridNERService(llm_service, use_spacy=True)
hybrid_service.load_gazetteer(actors)
results = hybrid_service.extract_actors(text, use_llm=True)
```

**Производительность**: ~500 текстов/сек (spaCy) + улучшение через LLM  
**Точность**: ~85-92% F1  
**Стоимость**: ~$0.0005-0.005 за 1000 текстов (LLM только для сложных случаев)

---

### Стратегия 4: Двухэтапная обработка

**Когда использовать**:
- Критически важна точность
- Можно позволить асинхронную обработку

**Код**:
```python
# Этап 1: Быстрое извлечение через spaCy
spacy_service = NERSpacyService()
spacy_results = spacy_service.extract_actors_from_text(text)

# Этап 2: Асинхронное улучшение через LLM
if need_improvement(spacy_results):
    llm_results = llm_service.extract_actors(text)
    final_results = merge_results(spacy_results, llm_results)
else:
    final_results = spacy_results
```

## Интеграция в существующую систему

### Вариант 1: Замена текущего LLM сервиса

В `backend/api/routes.py`:

```python
from backend.services.ner_spacy_service import HybridNERService

# Вместо прямого использования LLM
# actors = llm.extract_actors(text)

# Использовать гибридный сервис
hybrid_service = HybridNERService(llm, use_spacy=True)
hybrid_service.load_gazetteer(list(graph_manager.actors.values()))
actors = hybrid_service.extract_actors(text)
```

### Вариант 2: Добавление как альтернативного метода

Добавить новый endpoint:

```python
@app.post("/api/news/{news_id}/actors/extract-hybrid")
async def extract_actors_hybrid(news_id: str):
    """Извлечение акторов гибридным методом"""
    news = graph_manager.news.get(news_id)
    if not news:
        raise HTTPException(status_code=404)
    
    text = f"{news.title}\n{news.summary}\n{news.full_text}"
    
    # Гибридное извлечение
    llm_service = LLMService(api_key=os.getenv("GEMINI_API_KEY"))
    hybrid_service = HybridNERService(llm_service, use_spacy=True)
    hybrid_service.load_gazetteer(list(graph_manager.actors.values()))
    
    actors = hybrid_service.extract_actors(text)
    
    return {"actors": actors, "method": "hybrid"}
```

### Вариант 3: Конфигурируемый выбор метода

```python
NER_METHOD = os.getenv("NER_METHOD", "llm")  # llm, spacy, hybrid

if NER_METHOD == "spacy":
    service = NERSpacyService()
elif NER_METHOD == "hybrid":
    service = HybridNERService(llm_service, use_spacy=True)
else:
    service = llm_service  # По умолчанию LLM
```

## Сравнение производительности

| Метод | Скорость | Точность | Стоимость | Рекомендация |
|-------|----------|----------|-----------|--------------|
| Базовый NERService | Очень быстро | 50-60% F1 | $0 | Только для прототипа |
| spaCy | Быстро | 70-80% F1 | $0 | Для больших объемов |
| LLM (Gemini) | Средне | 89% F1 | $0.001-0.01/1k | Для точности |
| Гибридный | Быстро-средне | 85-92% F1 | $0.0005-0.005/1k | **Рекомендуется** |

## Примеры использования

См. файл `examples/ner_integration_example.py` для полного примера сравнения всех методов.

Запуск:
```bash
python examples/ner_integration_example.py
```

## Troubleshooting

### spaCy модель не загружается

```bash
# Проверить установленные модели
python -m spacy info

# Переустановить модель
python -m spacy download ru_core_news_lg --force
```

### Низкая точность spaCy

- Используйте большую модель (lg вместо sm)
- Добавьте кастомный gazetteer
- Рассмотрите fine-tuning модели на ваших данных

### Проблемы с производительностью

- Используйте меньшую модель (sm вместо lg)
- Обрабатывайте тексты батчами
- Кэшируйте результаты

## Дальнейшие улучшения

1. **Fine-tuning spaCy модели** на ваших данных
2. **Entity Linking** через знания базы (Wikidata, DBpedia)
3. **Ансамбль методов** - голосование между spaCy и LLM
4. **Асинхронная обработка** для больших объемов

