# Data Pipeline (план)

## Форматы
- Сырой источник: фид/соцсети/RSS — json с полями source, title, summary, url, published_at, full_text.
- Нормализованный документ: news {id, title, summary, full_text, source, published_at, domains[], mentioned_actors[], embedding, story_id?, is_duplicate}.
- Event: {id, news_id, story_id, event_type (fact/opinion), title, description, event_date, actors[], source_trust, confidence}.

## Этапы (позже, в ingestion module)
1) Fetch (коннекторы RSS/соцсети/Google News) + ретраи/логирование.
2) Normalize (язык, кодировка, обрезка, dedup).
3) Enrich: embeddings, NER, события, домены.
4) Persist: запись в граф (`GraphManager`), обновление историй/связей.

## На мок-данных
- Хранение в `data/*.json`.
- Генерация событий из новостей при загрузке.
- Кэш результатов мок-LLM (summary/bullets/actors/events/domains) для стабильности демо.


