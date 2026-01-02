# Настройка генерации эмбеддингов

## Обзор

Система поддерживает три режима генерации эмбеддингов:

1. **Local (sentence-transformers)** - локальная модель, быстрая, бесплатная (рекомендуется для production)
2. **Gemini API** - облачный сервис Google (требует API ключ, в разработке)
3. **Mock** - мок-эмбеддинги для прототипирования (только для тестирования)

**Статус**: ✅ Реализовано и протестировано (2026-01-02)
- Локальный бэкенд работает стабильно
- Настройка доступна через UI (LLM Settings)
- Все существующие данные пересчитаны на реальные эмбеддинги

## Быстрый старт

### 1. Локальный подход (рекомендуется)

```bash
# Установить зависимости (уже в requirements.txt)
pip install sentence-transformers

# Установить переменную окружения
export EMBEDDING_BACKEND=local

# Или в .env файле:
echo "EMBEDDING_BACKEND=local" >> .env
```

При первом запуске модель `all-MiniLM-L6-v2` будет автоматически загружена (около 80MB).

### 2. Облачный подход (Gemini API)

```bash
# Установить API ключ
export GEMINI_API_KEY=your_api_key_here
export EMBEDDING_BACKEND=gemini

# Или в .env файле:
echo "GEMINI_API_KEY=your_api_key_here" >> .env
echo "EMBEDDING_BACKEND=gemini" >> .env
```

**Примечание**: Gemini API для embeddings находится в разработке. Текущая реализация может использовать fallback.

### 3. Мок-режим (по умолчанию)

```bash
export EMBEDDING_BACKEND=mock
# или просто не устанавливать переменную
```

## Сравнение подходов

### Локальный (sentence-transformers)

**Преимущества:**
- ✅ Быстро (10-100 текстов/сек на CPU)
- ✅ Бесплатно
- ✅ Работает офлайн
- ✅ Нет лимитов API
- ✅ Приватность (данные не отправляются в облако)

**Недостатки:**
- ⚠ Требует ~80MB дискового пространства для модели
- ⚠ Первая загрузка модели может занять время
- ⚠ Использует память для модели

**Рекомендуется для:**
- Production deployment
- Большие объемы данных
- Требования приватности

### Gemini API

**Преимущества:**
- ✅ Не требует локальных ресурсов
- ✅ Масштабируемость
- ✅ Обновления модели автоматически

**Недостатки:**
- ⚠ Требует API ключ
- ⚠ Зависит от интернета
- ⚠ Может иметь лимиты и стоимость
- ⚠ Задержка сети

**Рекомендуется для:**
- Cloud deployment
- Когда локальные ресурсы ограничены
- Когда нужны последние модели

### Мок-режим

**Использование:**
- Прототипирование
- Тестирование
- Разработка без зависимостей

**Не рекомендуется для:**
- Production
- Реальные вычисления similarity

## Бенчмарк

Запустите бенчмарк для сравнения производительности:

```bash
python scripts/benchmark_embeddings.py
```

Бенчмарк покажет:
- Скорость генерации (текстов/сек)
- Время инициализации
- Размерность эмбеддингов
- Сравнение качества (для mock vs local)

## Пересчет существующих эмбеддингов

Если вы переключаетесь с mock на реальные эмбеддинги, пересчитайте существующие данные:

```bash
# Пересчитать все новости без эмбеддингов
python scripts/recompute_embeddings.py --backend local

# Пересчитать все новости (даже с существующими эмбеддингами)
python scripts/recompute_embeddings.py --backend local --force

# Обработать только первые 100 новостей
python scripts/recompute_embeddings.py --backend local --limit 100

# Использовать батчи по 64 элемента
python scripts/recompute_embeddings.py --backend local --batch-size 64
```

## Интеграция в код

### Автоматическое использование

Система автоматически использует настройки из переменных окружения:

```python
from backend.services.embedding_service import EmbeddingService

# Использует EMBEDDING_BACKEND из env
service = EmbeddingService()
embeddings = service.encode(["Text 1", "Text 2"])
```

### Явное указание бэкенда

```python
# Локальный
service = EmbeddingService(backend="local")

# Gemini
service = EmbeddingService(backend="gemini", api_key="your_key")

# Mock
service = EmbeddingService(backend="mock")
```

## Проверка работы

### Проверка текущего бэкенда

```python
from backend.services.embedding_service import EmbeddingService

service = EmbeddingService()
print(f"Backend: {service.backend}")
print(f"Dimension: {service.get_embedding_dimension()}")
```

### Тест генерации

```python
service = EmbeddingService(backend="local")
texts = ["Test text 1", "Test text 2"]
embeddings = service.encode(texts)
print(f"Generated {len(embeddings)} embeddings of dimension {embeddings.shape[1]}")
```

## Troubleshooting

### Ошибка: sentence-transformers not installed

```bash
pip install sentence-transformers
```

### Ошибка: Model download failed

Проверьте интернет-соединение. Модель загружается автоматически при первом использовании.

### Ошибка: GEMINI_API_KEY not set

Для Gemini API требуется API ключ. Получите его на [Google AI Studio](https://makersuite.google.com/app/apikey).

### Медленная генерация

- Используйте батчи: `service.encode(texts, batch_size=32)`
- Для больших объемов рассмотрите GPU (если доступно)
- Проверьте, что не используется mock-режим

### Несоответствие размерности

Разные бэкенды могут генерировать эмбеддинги разной размерности:
- Local (MiniLM): 384
- Gemini: 768 (если доступно)
- Mock: 384

При переключении бэкендов может потребоваться пересчет всех эмбеддингов.

## UI Настройка

Настройка embedding backend доступна через UI:

1. Откройте приложение
2. Нажмите кнопку **"LLM Settings"** в заголовке
3. В секции **"Embedding Backend"** выберите нужный бэкенд:
   - **Local (sentence-transformers)** - для production
   - **Gemini API** - для облачного использования
   - **Mock** - только для тестирования
4. Нажмите **"Save"**

Изменения применяются немедленно (некоторые операции могут потребовать перезапуска сервера).

В модалке отображается текущий статус и размерность эмбеддингов.

## API Endpoints

### Получить текущий бэкенд
```bash
GET /api/embedding/backend
```

Ответ:
```json
{
  "backend": "local",
  "dimension": 384,
  "model_name": "all-MiniLM-L6-v2"
}
```

### Установить бэкенд
```bash
PUT /api/embedding/backend
Content-Type: application/json

{
  "backend": "local"
}
```

Ответ:
```json
{
  "backend": "local",
  "dimension": 384,
  "model_name": "all-MiniLM-L6-v2",
  "message": "Embedding backend updated. Some operations may require server restart."
}
```

**Важно**: При ошибке инициализации (например, не установлен sentence-transformers) API вернет ошибку 500 с описанием проблемы. Fallback на mock отключен для предотвращения использования некачественных эмбеддингов.

## Рекомендации

1. **Для production**: Используйте `EMBEDDING_BACKEND=local` или настройте через UI
2. **Для разработки**: Можно использовать `mock` для быстрого тестирования
3. **Для облака**: Рассмотрите `gemini` если локальные ресурсы ограничены
4. **При миграции**: Всегда пересчитывайте эмбеддинги при смене бэкенда

## Дополнительная информация

- [sentence-transformers документация](https://www.sbert.net/)
- [Gemini API документация](https://ai.google.dev/docs)
- [Roadmap: Задача 2.6](../roadmap.md#задача-26)
- [Результаты бенчмарка](embeddings_benchmark_results.md)

