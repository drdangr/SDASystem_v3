# Backend (FastAPI)

## Структура
- `backend/api/routes.py` — основные REST-эндпоинты: истории, новости, акторы, события, граф.
- `backend/api/graph_routes.py` — адаптация данных графа для фронтенда.
- Services:
  - `GraphManager` — хранение графов news/actors/mentions, истории, события.
  - `EventExtractionService` — извлечение событий из новостей (датчики, тип события).
  - `EmbeddingService`, `NERService`, `ClusteringService` — мок/заглушки для демо.
- Data: загрузка из `data/*.json`, вычисление связей при старте.

## Ключевые модели
- `News`, `Actor`, `Story`, `Event`, `NewsRelation`, `ActorRelation` (`backend/models/entities.py`).
- Метрики сюжета: relevance, cohesion, size, freshness; домены и топ-акторы.

## Потоки
- Инициализация: `load_data()` → акторы → новости → сюжеты → compute similarities.
- Таймлайн: `/api/stories/{id}/events` отдаёт `GraphManager.get_story_events(story_id)`.
- Отношения: `/api/actors/{id}/relations`, `/api/actors/{id}/mentions`.

## TODO для прототипа
- Генерация событий при загрузке мок-данных через `EventExtractionService`, обновление `story.event_ids`.
- Фолбэк дат на `published_at`, поддержка RU/EN выражений.
- Кэш/детерминированность мок-сервисов, чтобы UI был стабильным.


