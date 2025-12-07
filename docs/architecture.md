# Архитектура SDAS

## Обзор
- **Двухслойный граф**: новости (контент) и акторы (NER), связки news↔news, actor↔actor, news↔actor.
- **Сюжеты (Stories)**: динамические кластеры новостей с метриками relevance, cohesion, size, freshness.
- **Таймлайн событий**: цепочки событий внутри сюжета с классификацией fact/opinion.
- **Мультиязычность**: поддержка английского и русского языков с канонизацией сущностей.

## Компоненты

### Backend (FastAPI)
*   **API**: REST endpoints (`/api/stories`, `/api/news`, `/api/actors`, `/api/graph/*`).
*   **Core Services**:
    *   `GraphManager`: Управление графом в памяти (NetworkX).
    *   `ClusteringService`: Кластеризация новостей в сюжеты.
    *   `EmbeddingService`: Векторизация текстов.
*   **AI & NLP Pipeline**:
    *   `HybridNERService`: Извлечение сущностей (spaCy + LLM Gemini).
    *   `ActorCanonicalizationService`: Нормализация, лемматизация (spaCy ru/en), обогащение (Wikidata).
    *   `ActorsExtractionService`: Оркестрация, дедупликация и обновление графа.
    *   `LLMService`: Абстракция над провайдерами (Gemini), кэширование.
*   **External Integrations**:
    *   Wikidata API (для метаданных и QID).
    *   Gemini API (для генерации и NER).

### Frontend (Vanilla JS + Modules)
*   **Views**: `ListView`, `GraphView`, `StoryView`, `DetailsView`, `TimelineView`.
*   **Architecture**: Модульная, EventBus для связки компонентов, State Management.
*   **Visualization**: D3.js (Force Graph), Vis.js (Timeline).

## Потоки Данных (Data Flow)
1.  **Ingestion**: (Planned) Сбор и нормализация новостей.
2.  **Processing**:
    *   Генерация эмбеддингов.
    *   NER: Hybrid Extract -> Canonicalize (Wikidata) -> Deduplicate -> Update Graph.
3.  **Clustering**: Группировка новостей в сюжеты.
4.  **Serving**: API отдает готовые структуры для UI.

## Расширяемость
Архитектура модульная. Новые сервисы (например, Sentiment Analysis) могут подключаться как пайплайн-шаги перед обновлением графа.
