"""
Тесты для ActorCanonicalizationService
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.services.actor_canonicalization_service import ActorCanonicalizationService


class TestActorCanonicalizationService:
    """Тесты для сервиса канонизации акторов"""
    
    @pytest.fixture
    def service(self):
        """Создать экземпляр сервиса для тестов"""
        return ActorCanonicalizationService(
            use_wikidata=False,  # Отключаем Wikidata для unit-тестов
            use_lemmatization=True
        )
    
    def test_russian_lemmatization(self, service):
        """Тест лемматизации русских склонений"""
        # Тестируем различные склонения
        test_cases = [
            ("Украиной", "Украина"),
            ("Россией", "Россия"),
            ("России", "Россия"),
            ("Украину", "Украина"),
        ]
        
        for input_name, expected_base in test_cases:
            # Используем реальную модель spaCy если доступна
            result = service._lemmatize_russian(input_name)
            # Проверяем что результат содержит базовую форму
            # (может быть с заглавной буквой)
            assert expected_base.lower() in result.lower() or result.lower() in expected_base.lower(), \
                f"Failed: {input_name} -> {result}, expected contains {expected_base}"
    
    def test_normalize_russian_name(self, service):
        """Тест нормализации русских имен"""
        result = service._normalize_russian_name("украиной")
        # Должно быть с заглавной буквы
        assert result[0].isupper() if result else True
    
    def test_canonicalize_with_wikidata(self):
        """Тест канонизации через Wikidata"""
        service = ActorCanonicalizationService(
            use_wikidata=True,
            use_lemmatization=False  # Отключаем для простоты теста
        )
        
        # Мокаем Wikidata сервис
        mock_wikidata_result = {
            "qid": "Q7747",
            "canonical_name": "Владимир Путин",
            "aliases": [
                {"name": "Putin", "type": "alias", "language": "en"},
                {"name": "Путин", "type": "alias", "language": "ru"}
            ],
            "metadata": {
                "positions": ["Президент России"],
                "country": "Россия"
            }
        }
        
        with patch.object(service, '_wikidata_service') as mock_wikidata:
            mock_wikidata.search_entity = Mock(return_value=mock_wikidata_result)
            
            result = service.canonicalize_actor("Путин", "person", "ru")
            
            assert result["canonical_name"] == "Владимир Путин"
            assert result["wikidata_qid"] == "Q7747"
            assert len(result["aliases"]) > 0
            assert "positions" in result["metadata"]
    
    def test_canonicalize_fallback(self, service):
        """Тест fallback без Wikidata"""
        # Без Wikidata должен использовать лемматизацию
        result = service.canonicalize_actor("Украиной", "country", "ru")
        
        assert result["canonical_name"] is not None
        assert result["canonical_name"] != "Украиной"  # Должно быть нормализовано
        assert result["original_name"] == "Украиной"
        assert len(result["aliases"]) > 0  # Оригинальное имя должно быть в алиасах
    
    def test_batch_canonicalization(self, service):
        """Тест пакетной обработки акторов"""
        actors = [
            {"name": "Украиной", "type": "country", "confidence": 0.9},
            {"name": "Россией", "type": "country", "confidence": 0.9},
            {"name": "Владимир Путин", "type": "person", "confidence": 0.95}
        ]
        
        canonicalized = service.canonicalize_batch(actors)
        
        assert len(canonicalized) == 3
        for item in canonicalized:
            assert "canonical_name" in item
            assert "aliases" in item
            assert "metadata" in item
    
    def test_alias_extraction(self):
        """Тест извлечения русских и английских алиасов"""
        service = ActorCanonicalizationService(
            use_wikidata=True,
            use_lemmatization=False
        )
        
        mock_wikidata_result = {
            "qid": "Q159",
            "canonical_name": "Россия",
            "aliases": [
                {"name": "Russia", "type": "alias", "language": "en"},
                {"name": "РФ", "type": "alias", "language": "ru"},
                {"name": "Russian Federation", "type": "alias", "language": "en"}
            ],
            "metadata": {}
        }
        
        with patch.object(service, '_wikidata_service') as mock_wikidata:
            mock_wikidata.search_entity = Mock(return_value=mock_wikidata_result)
            
            result = service.canonicalize_actor("Россией", "country", "ru")
            
            # Должны быть алиасы на русском и английском
            alias_languages = [a.get("language") for a in result["aliases"]]
            assert "ru" in alias_languages or "en" in alias_languages
    
    def test_metadata_enrichment(self):
        """Тест обогащения метаданными"""
        service = ActorCanonicalizationService(
            use_wikidata=True,
            use_lemmatization=False
        )
        
        mock_wikidata_result = {
            "qid": "Q7747",
            "canonical_name": "Владимир Путин",
            "aliases": [],
            "metadata": {
                "positions": ["Президент России"],
                "country": "Россия",
                "birth_date": "+1952-10-07T00:00:00Z"
            }
        }
        
        with patch.object(service, '_wikidata_service') as mock_wikidata:
            mock_wikidata.search_entity = Mock(return_value=mock_wikidata_result)
            
            result = service.canonicalize_actor("Путин", "person", "ru")
            
            metadata = result["metadata"]
            assert "positions" in metadata
            assert "country" in metadata
            assert metadata["country"] == "Россия"

