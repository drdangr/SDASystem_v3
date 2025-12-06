# Release Notes (шаблон)

## v0.1.0 (prototype, mock data)
- Базовый UI: список/граф сюжетов, карточка сюжета, детали новости/актора, таймлайн.
- Мок-данные в `data/`.

## v0.2.0 (full mock feature parity, planned)
- Таймлайн с событиями (fact/opinion), зум и состояния загрузки.
- Метрики сюжета в UI, стабилизация панелей и resizer.
- Заглушки LLM для summary/bullets/actors/events/domains.
- Тесты backend (services, API) и UI чек-листы.

## v0.3.0 (LLM integration on mock data, planned)
- Реальные вызовы LLM для суммаризации/NER/ивентов/доменов, кэш результатов.
- Контрактные тесты и деградация при ошибках.

## v0.4.0 (ingestion module, planned)
- Модуль сбора новостей (RSS/соцсети/Google News), нормализация, дедупликация.
- E2E ingest → enrich → graph update на тестовом наборе.


