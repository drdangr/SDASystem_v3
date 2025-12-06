# Архитектура SDAS

## Обзор
- Двухслойный граф: новости (контент) и акторы (NER), связки news↔news, actor↔actor, news↔actor.
- Сюжеты (stories) как кластеры новостей с метриками relevance/cohesion/size/freshness.
- Таймлайн событий внутри сюжета (fact/opinion) с датами.
- UI: список/граф сюжетов, карточка сюжета, детали новости/актора, таймлайн.

## Компоненты
- Backend (FastAPI):
  - API: `/api/stories`, `/api/news`, `/api/actors`, `/api/stories/{id}/events`, `/api/graph/*`.
  - Services: `GraphManager`, `EventExtractionService`, `EmbeddingService`, `NERService`, `ClusteringService`.
  - Data: загрузка мок-данных из `data/`, хранение графа в памяти.
- Frontend (vanilla JS + modules):
  - Views: `ListView`, `GraphView`, `StoryView`, `DetailsView`, `TimelineView`.
  - EventBus для связки панелей, `app.js` orchestrator.
  - Шаблон `frontend/templates/index.html`, стили в `static/css`.

## Потоки данных
- Загрузка: `load_data()` → акторы, новости, сюжеты → вычисление связей.
- Выбор сюжета: запрос деталей и событий → обновление UI панелей.
- Таймлайн: `/api/stories/{id}/events` возвращает готовые `Event` объекты.

## Расширения
- LLM-интеграции: суммаризация, буллеты, NER, события, домены.
- Модуль ingestion: сбор новостей, нормализация, дедупликация, обогащение.


