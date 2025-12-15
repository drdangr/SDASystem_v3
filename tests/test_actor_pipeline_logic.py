import pytest
from unittest.mock import MagicMock, patch
from backend.models.entities import News, Actor, ActorType
from backend.services.actors_extraction_service import ActorsExtractionService
from backend.services.graph_manager import GraphManager
from backend.services.llm_service import LLMService
from datetime import datetime

class TestActorPipelineLogic:
    @pytest.fixture
    def mock_graph_manager(self):
        gm = MagicMock(spec=GraphManager)
        gm.actors = {}
        gm.news = {}
        gm.stories = {}
        gm.mentions_graph = MagicMock()
        # Mock methods
        gm.add_actor = lambda actor: gm.actors.update({actor.id: actor})
        return gm

    @pytest.fixture
    def mock_llm_service(self):
        llm = MagicMock(spec=LLMService)
        # Default mock response
        llm.extract_actors.return_value = []
        return llm

    @pytest.fixture
    def service(self, mock_graph_manager, mock_llm_service):
        # We use real ActorsExtractionService but with mocked dependencies
        # preventing actual file IO or heavy model loading where possible
        with patch('backend.services.actors_extraction_service.GoogleNERService') as MockHybrid, \
             patch('backend.services.actors_extraction_service.ActorCanonicalizationService') as MockCanon:
            
            service = ActorsExtractionService(
                graph_manager=mock_graph_manager,
                llm_service=mock_llm_service,
                use_spacy=False # Disable real spaCy loading for speed in this logic test
            )
            
            # Setup mocks for internal services
            service.hybrid = MockHybrid.return_value
            service.canonicalization_service = MockCanon.return_value
            
            return service

    def test_flow_step_2_language_detection(self):
        """Test language detection logic (Step 2)"""
        from backend.services.ner_spacy_service import detect_language
        
        assert detect_language("Hello world") == "en"
        assert detect_language("Привет мир") == "ru"
        assert detect_language("Привіт світе") == "uk"
        assert detect_language("Ukraine is a country. Украина - это страна.") == "ru" # Mixed, dominant Cyrillic? Or presence.
        
    def test_flow_step_3_extraction_orchestration(self, service):
        """Test extraction calling logic (Step 3)"""
        news = News(
            id="news_1",
            title="Test News",
            summary="Summary",
            full_text="Full text content",
            source="test",
            published_at=datetime.now()
        )
        
        # Setup mock return from HybridNER
        service.hybrid.extract_actors.return_value = [
            {"name": "Entity1", "type": "organization", "confidence": 0.9}
        ]
        
        # Setup mock return from Canonicalization (pass-through for now)
        service.canonicalization_service.canonicalize_batch.return_value = [
            {"name": "Entity1", "canonical_name": "Entity1", "type": "organization", "confidence": 0.9}
        ]
        
        service.extract_for_news(news)
        
        # Verify HybridNER was called (Step 3)
        service.hybrid.extract_actors.assert_called_once()
        args = service.hybrid.extract_actors.call_args
        assert "Full text content" in args[0][0] or "Test News" in args[0][0]

    def test_flow_step_4_processing_canonicalization(self, service):
        """Test processing: canonicalization and metadata enrichment (Step 4)"""
        news = News(id="n1", title="T", summary="S", source="test", published_at=datetime.now())
        
        # Raw extracted
        raw_actors = [
            {"name": "Украиной", "type": "country", "confidence": 0.8}
        ]
        service.hybrid.extract_actors.return_value = raw_actors
        
        # Mock Canonicalization Service response
        service.canonicalization_service.canonicalize_batch.return_value = [
            {
                "name": "Украиной",
                "canonical_name": "Украина", # Canonicalized
                "type": "country",
                "confidence": 0.8,
                "wikidata_qid": "Q212",
                "aliases": [{"name": "Украиной", "type": "original"}],
                "metadata": {"country": "Ukraine"}
            }
        ]
        
        actors, ids = service.extract_for_news(news)
        
        # Verify Canonicalization was called
        service.canonicalization_service.canonicalize_batch.assert_called_with(raw_actors, default_language="en")
        
        # Verify Actor was created with canonical data
        added_actor = service.graph_manager.actors[ids[0]]
        assert added_actor.canonical_name == "Украина"
        assert added_actor.wikidata_qid == "Q212"
        assert added_actor.metadata["country"] == "Ukraine"

    def test_flow_step_4_deduplication(self, service):
        """Test deduplication logic (Step 4 part 2)"""
        # Scenario: "Ukraine" exists, we extract "Ukraine" again
        
        # 1. Add existing actor
        existing = Actor(id="a1", canonical_name="Ukraine", actor_type=ActorType.COUNTRY)
        service.graph_manager.add_actor(existing)
        
        news = News(id="n1", title="T", summary="S", source="test", published_at=datetime.now())
        
        # Extracted again
        service.hybrid.extract_actors.return_value = [{"name": "Ukraine", "type": "country"}]
        service.canonicalization_service.canonicalize_batch.return_value = [
            {"name": "Ukraine", "canonical_name": "Ukraine", "type": "country"}
        ]
        
        actors, ids = service.extract_for_news(news)
        
        # Should reuse existing ID
        assert ids[0] == "a1"
        assert len(service.graph_manager.actors) == 1

    def test_mixed_language_scenario(self, service):
        """Test mixed language handling"""
        # Existing English actor
        existing = Actor(id="a1", canonical_name="Donald Trump", actor_type=ActorType.PERSON, wikidata_qid="Q22686")
        service.graph_manager.add_actor(existing)
        
        news = News(id="n_ru", title="Ру", summary="Трамп сказал", source="test", published_at=datetime.now())
        
        # Extracted Russian "Трамп"
        service.hybrid.extract_actors.return_value = [{"name": "Трамп", "type": "person"}]
        
        # Canonicalization maps "Трамп" -> Q22686
        service.canonicalization_service.canonicalize_batch.return_value = [
            {
                "name": "Трамп",
                "canonical_name": "Дональд Трамп", 
                "type": "person",
                "wikidata_qid": "Q22686", # Same QID
                "aliases": [{"name": "Трамп"}] 
            }
        ]
        
        actors, ids = service.extract_for_news(news)
        
        # Should map to existing actor due to QID match or canonical name match logic
        # (Logic in _add_or_get_actor_with_canonicalization handles QID check)
        assert ids[0] == "a1"
        
        # Verify alias was added
        updated_actor = service.graph_manager.actors["a1"]
        alias_names = [a['name'] for a in updated_actor.aliases]
        assert "Трамп" in alias_names


