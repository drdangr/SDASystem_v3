# Frontend (UI)

## Структура
- `frontend/templates/index.html` — каркас приложения, панели и таймлайн.
- `frontend/static/js/app.js` — инициализация, выбор сюжета/новости/актора, EventBus.
- Views:
  - `ListView` — список сюжетов.
  - `GraphView` — граф новостей по сюжету или общий.
  - `StoryView` — карточка сюжета (буллеты, топ-акторы, связанные новости).
  - `DetailsView` — детали новости или актора.
  - `TimelineView` — события сюжета (fact/opinion), зум.
- Стили: `static/css/styles.css`, `graph-styles.css`.

## Потоки UI
1) Загрузка историй → рендер списка/графа → автоселект первой истории.
2) Клик по сюжету → StoryView, TimelineView, очистка DetailsView.
3) Клик по новости/актору → DetailsView с подгрузкой `/api/news/{id}` или `/api/actors/{id}`.
4) Таймлайн зум-кнопки меняют режим отображения (day/week/month, TODO: группировка).

## TODO для прототипа (мок)
- Покрыть все метрики сюжета (relevance, cohesion, size, freshness, домены).
- Стабильные состояния панелей, resizer, сохранение в `localStorage`.
- Цветовое кодирование событий fact/opinion, стейты загрузки/пусто/ошибка.
- Заглушки LLM: summary, bullets, actors, events, domains — чтобы UI всегда заполнялся.


