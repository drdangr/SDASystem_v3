# Testing Strategy

## Уровни
- Юнит: `GraphManager`, `EventExtractionService`, `ClusteringService`, утилиты.
- Контрактные/интеграционные: FastAPI маршруты (stories, news, actors, events, graph).
- UI чек-листы: список/граф, карточка сюжета, детали новости/актора, таймлайн, панели.

## Покрытие для мок-прототипа
- Генерация событий из мок-новостей → есть `event_ids` в историях.
- Метрики сюжета отображаются в UI (relevance, cohesion, size, freshness).
- Состояния загрузки/пусто/ошибка в TimelineView.

## Тестовые данные
- Использовать `data/*.json` (акторы, новости, сюжеты) как фикстуры.
- Для контрактных тестов API — мок сервисов LLM/NER/Embeddings.

## Инструменты
- Pytest для backend, Playwright/ручные чек-листы для UI.
- Lint/format (ruff/flake8, eslint/prettier при необходимости).


