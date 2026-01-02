# Backend (FastAPI)

## Структура
- `backend/api/routes.py` — основные REST-эндпоинты: истории, новости, акторы, события, граф.
- `backend/api/graph_routes.py` — адаптация данных графа для фронтенда.
- Services:
  - `DatabaseManager` — слой доступа к PostgreSQL + pgvector (CRUD, векторный поиск).
  - `GraphManager` — управление графами news/actors/mentions, истории, события (использует DatabaseManager).
  - `EventExtractionService` — извлечение событий из новостей (датчики, тип события).
  - `EmbeddingService`, `NERService`, `ClusteringService` — сервисы обработки данных.
- Data: хранение в PostgreSQL, загрузка из БД при старте (fallback на JSON для миграции).

## Ключевые модели
- `News`, `Actor`, `Story`, `Event`, `NewsRelation`, `ActorRelation` (`backend/models/entities.py`).
- Метрики сюжета: relevance, cohesion, size, freshness; домены и топ-акторы.

## Потоки
- Инициализация: `load_data()` → проверка БД → загрузка из БД или JSON (миграция) → построение графов.
- Таймлайн: `/api/stories/{id}/events` отдаёт `DatabaseManager.get_story_events(story_id)`.
- Отношения: `/api/actors/{id}/relations`, `/api/actors/{id}/mentions` — через DatabaseManager.
- Векторный поиск: `DatabaseManager.compute_news_similarities()` использует pgvector для эффективного поиска похожих новостей.

## База данных
- PostgreSQL 12+ с расширением pgvector
- Схема: 15 таблиц (news, actors, stories events domains + связующие таблицы)
- Векторный индекс на `news.embedding` для быстрого поиска похожих новостей
- Подробнее: [docs/database_schema.md](../database_schema.md), [docs/database_setup.md](../database_setup.md)

## Тестирование
- **DatabaseManager**: полный набор из 36 юнит-тестов (`tests/test_database_manager.py`)
  - CRUD операции для всех сущностей (News, Actor, Story, Event)
  - Связи между сущностями (news-actors, story-news, story-actors, story-events, event-actors)
  - Векторный поиск с использованием pgvector
  - Транзакции и пул соединений
  - Интеграционные сценарии (полный workflow)
  - Граничные случаи (пустые данные, несуществующие записи, длинные тексты)
  - Производительность (массовая вставка, векторный поиск)
- Все тесты пройдены (36/36)
- Отчет: [docs/database_tests_report.md](../database_tests_report.md)

## TODO для прототипа
- Генерация событий при загрузке мок-данных через `EventExtractionService`, обновление `story.event_ids`.
- Фолбэк дат на `published_at`, поддержка RU/EN выражений.
- Кэш/детерминированность мок-сервисов, чтобы UI был стабильным.


