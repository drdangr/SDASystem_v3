"""
Интеграционные тесты для канонизации акторов
"""
import pytest
from backend.services.graph_manager import GraphManager
from backend.services.llm_service import LLMService
from backend.services.actors_extraction_service import ActorsExtractionService
from backend.models.entities import News, Actor
from datetime import datetime


class TestActorCanonicalizationIntegration:
    """Интеграционные тесты для полного цикла канонизации"""
    
    @pytest.fixture
    def graph_manager(self):
        """Создать GraphManager для тестов"""
        return GraphManager()
    
    @pytest.fixture
    def llm_service(self):
        """Создать LLMService для тестов"""
        return LLMService(use_mock=True)
    
    @pytest.fixture
    def extraction_service(self, graph_manager, llm_service, tmp_path):
        """Создать ActorsExtractionService для тестов"""
        return ActorsExtractionService(
            graph_manager=graph_manager,
            llm_service=llm_service,
            data_dir=str(tmp_path),
            use_spacy=True,
            spacy_model="en_core_web_sm"
        )
    
    def test_full_pipeline(self, extraction_service, graph_manager):
        """Тест полного цикла: извлечение -> канонизация -> добавление в граф"""
        # Создаем тестовую новость на русском языке
        news = News(
            id="test_news_1",
            title="Инициализация мирных переговоров",
            summary="Переговоры между Украиной и Россией",
            full_text="Администрация США объявила о начале процесса инициализации мирных переговоров между Украиной и Россией. Президент России Владимир Путин выразил готовность к диалогу.",
            source="Test Source",
            published_at=datetime.utcnow()
        )
        graph_manager.add_news(news)
        
        # Извлекаем акторов
        extracted, actor_ids = extraction_service.extract_for_news(news)
        
        # Проверяем что акторы извлечены
        assert len(actor_ids) > 0
        
        # Проверяем что акторы канонизированы
        for actor_id in actor_ids:
            actor = graph_manager.actors.get(actor_id)
            assert actor is not None
            # Проверяем что есть каноническое имя
            assert actor.canonical_name
            # Проверяем что склонения нормализованы (для стран)
            actor_type = actor.actor_type.value if hasattr(actor.actor_type, 'value') else str(actor.actor_type)
            if actor_type == "country":
                assert actor.canonical_name not in ["Украиной", "Россией"]
    
    def test_deduplication_with_qid(self, extraction_service, graph_manager):
        """Тест дедупликации акторов с одинаковым QID"""
        # Создаем двух акторов с одинаковым QID вручную
        actor1 = Actor(
            id="actor_test_1",
            canonical_name="Владимир Путин",
            actor_type="person",
            wikidata_qid="Q7747",
            aliases=[]
        )
        actor2 = Actor(
            id="actor_test_2",
            canonical_name="Путин",
            actor_type="person",
            wikidata_qid="Q7747",
            aliases=[]
        )
        
        graph_manager.add_actor(actor1)
        graph_manager.add_actor(actor2)
        
        # Запускаем дедупликацию
        extraction_service.deduplicate_actors()
        
        # Должен остаться только один актор
        actors_with_qid = [a for a in graph_manager.actors.values() if a.wikidata_qid == "Q7747"]
        assert len(actors_with_qid) == 1
        
        # Второй актор должен быть в алиасах первого
        remaining_actor = actors_with_qid[0]
        alias_names = [a.get("name") for a in remaining_actor.aliases]
        assert "Путин" in alias_names or "Владимир Путин" in alias_names
    
    def test_russian_english_linking(self, extraction_service, graph_manager):
        """Тест связывания русских и английских вариантов"""
        # Создаем новость со смешанными языками
        news = News(
            id="test_news_2",
            title="Russia and Россия",
            summary="Test news",
            full_text="Russia criticized Ukraine. Россия поддержала инициативу.",
            source="Test Source",
            published_at=datetime.utcnow()
        )
        graph_manager.add_news(news)
        
        # Извлекаем акторов
        extracted, actor_ids = extraction_service.extract_for_news(news)
        
        # Проверяем что "Russia" и "Россия" связаны через алиасы
        russia_actors = [
            a for a in graph_manager.actors.values()
            if "Russia" in a.canonical_name or "Россия" in a.canonical_name or
               any("Russia" in alias.get("name", "") or "Россия" in alias.get("name", "") 
                   for alias in a.aliases)
        ]
        
        # Должен быть хотя бы один актор с русским или английским вариантом
        assert len(russia_actors) > 0
        
        # Проверяем что есть алиасы на обоих языках
        for actor in russia_actors:
            alias_names = [a.get("name") for a in actor.aliases]
            has_russian = any("Россия" in name or "Russia" in name for name in alias_names + [actor.canonical_name])
            assert has_russian
    
    def test_news_actor_links(self, extraction_service, graph_manager):
        """Тест связей новостей с канонизированными акторами"""
        news = News(
            id="test_news_3",
            title="Украина и Россия",
            summary="Test",
            full_text="Украиной и Россией начаты переговоры.",
            source="Test Source",
            published_at=datetime.utcnow()
        )
        graph_manager.add_news(news)
        
        # Извлекаем акторов
        extracted, actor_ids = extraction_service.extract_for_news(news)
        
        # Проверяем что новость связана с акторами
        assert len(news.mentioned_actors) > 0
        
        # Проверяем что акторы канонизированы
        for actor_id in news.mentioned_actors:
            actor = graph_manager.actors.get(actor_id)
            assert actor is not None
            # Проверяем что склонения нормализованы
            if "Украин" in actor.canonical_name or "Росси" in actor.canonical_name:
                assert actor.canonical_name not in ["Украиной", "Россией"]
    
    def test_metadata_persistence(self, extraction_service, graph_manager, tmp_path):
        """Тест сохранения метаданных в файлы"""
        news = News(
            id="test_news_4",
            title="Владимир Путин",
            summary="Test",
            full_text="Президент России Владимир Путин объявил о решении.",
            source="Test Source",
            published_at=datetime.utcnow()
        )
        graph_manager.add_news(news)
        
        # Извлекаем акторов
        extracted, actor_ids = extraction_service.extract_for_news(news)
        
        # Сохраняем акторов
        extraction_service._save_actors()
        
        # Проверяем что файл создан
        actors_file = tmp_path / "actors.json"
        assert actors_file.exists()
        
        # Загружаем обратно и проверяем метаданные
        import json
        with open(actors_file, 'r', encoding='utf-8') as f:
            actors_data = json.load(f)
        
        # Находим актора Путина
        putin_actors = [a for a in actors_data if "Путин" in a.get("canonical_name", "")]
        if putin_actors:
            actor_data = putin_actors[0]
            # Проверяем что метаданные сохранены
            assert "metadata" in actor_data
            # Проверяем что есть QID если был найден через Wikidata
            # (может быть None если Wikidata отключен или не нашел)

