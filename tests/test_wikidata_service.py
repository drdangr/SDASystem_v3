"""
Тесты для WikidataService
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.services.wikidata_service import WikidataService


class TestWikidataService:
    """Тесты для сервиса Wikidata"""
    
    def test_search_entity_success(self):
        """Тест успешного поиска сущности"""
        service = WikidataService(cache_ttl=0)  # Отключаем кэш для тестов
        
        # Мокаем ответ от Wikidata API
        mock_response = Mock()
        mock_response.json.return_value = {
            "search": [
                {
                    "id": "Q7747",
                    "label": "Владимир Путин",
                    "description": "российский государственный деятель"
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('backend.services.wikidata_service.requests.get', return_value=mock_response):
            # Мокаем get_entity_info
            with patch.object(service, 'get_entity_info', return_value={
                "qid": "Q7747",
                "canonical_name": "Владимир Путин",
                "aliases": [{"name": "Putin", "type": "alias", "language": "en"}],
                "metadata": {"positions": ["Президент России"]}
            }):
                result = service.search_entity("Владимир Путин", "ru")
                
                assert result is not None
                assert result["qid"] == "Q7747"
                assert result["canonical_name"] == "Владимир Путин"
                assert len(result["aliases"]) > 0
    
    def test_search_entity_not_found(self):
        """Тест случая когда сущность не найдена"""
        service = WikidataService(cache_ttl=0)
        
        mock_response = Mock()
        mock_response.json.return_value = {"search": []}
        mock_response.raise_for_status = Mock()
        
        with patch('backend.services.wikidata_service.requests.get', return_value=mock_response):
            result = service.search_entity("НесуществующаяСущность12345", "ru")
            assert result is None
    
    def test_get_entity_info(self):
        """Тест получения полной информации о сущности"""
        service = WikidataService(cache_ttl=0)
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "entities": {
                "Q7747": {
                    "labels": {
                        "ru": {"value": "Владимир Путин"},
                        "en": {"value": "Vladimir Putin"}
                    },
                    "aliases": {
                        "ru": [{"value": "Путин"}],
                        "en": [{"value": "Putin"}]
                    },
                    "claims": {
                        "P39": [{
                            "mainsnak": {
                                "datavalue": {
                                    "type": "wikibase-entityid",
                                    "value": {"id": "Q11696"}
                                }
                            }
                        }]
                    },
                    "descriptions": {
                        "ru": {"value": "российский государственный деятель"}
                    }
                }
            }
        }
        mock_response.raise_for_status = Mock()
        
        with patch('backend.services.wikidata_service.requests.get', return_value=mock_response):
            # Мокаем _get_label_for_qid
            with patch.object(service, '_get_label_for_qid', return_value="Президент России"):
                result = service.get_entity_info("Q7747", "ru")
                
                assert result is not None
                assert result["qid"] == "Q7747"
                assert result["canonical_name"] == "Владимир Путин"
                assert len(result["aliases"]) > 0
                assert "metadata" in result
    
    def test_cache_mechanism(self):
        """Тест кэширования результатов"""
        service = WikidataService(cache_ttl=3600)  # 1 час
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "search": [{"id": "Q7747", "label": "Владимир Путин"}]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('backend.services.wikidata_service.requests.get', return_value=mock_response):
            with patch.object(service, 'get_entity_info', return_value={
                "qid": "Q7747",
                "canonical_name": "Владимир Путин",
                "aliases": [],
                "metadata": {}
            }):
                # Первый запрос - должен сделать API вызов
                result1 = service.search_entity("Владимир Путин", "ru")
                assert result1 is not None
                
                # Второй запрос - должен использовать кэш
                result2 = service.search_entity("Владимир Путин", "ru")
                assert result2 is not None
                assert result1 == result2
    
    def test_multilingual_aliases(self):
        """Тест извлечения алиасов на разных языках"""
        service = WikidataService(cache_ttl=0)
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "entities": {
                "Q159": {
                    "labels": {
                        "ru": {"value": "Россия"},
                        "en": {"value": "Russia"}
                    },
                    "aliases": {
                        "ru": [{"value": "РФ"}, {"value": "Российская Федерация"}],
                        "en": [{"value": "Russian Federation"}]
                    },
                    "claims": {},
                    "descriptions": {}
                }
            }
        }
        mock_response.raise_for_status = Mock()
        
        with patch('backend.services.wikidata_service.requests.get', return_value=mock_response):
            result = service.get_entity_info("Q159", "ru")
            
            assert result is not None
            aliases = result["aliases"]
            # Должны быть алиасы на русском и английском
            alias_names = [a["name"] for a in aliases]
            assert "РФ" in alias_names or "Russian Federation" in alias_names
    
    def test_metadata_extraction(self):
        """Тест извлечения метаданных (должности, страны)"""
        service = WikidataService(cache_ttl=0)
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "entities": {
                "Q7747": {
                    "labels": {"ru": {"value": "Владимир Путин"}},
                    "aliases": {},
                    "claims": {
                        "P39": [{
                            "mainsnak": {
                                "datavalue": {
                                    "type": "wikibase-entityid",
                                    "value": {"id": "Q11696"}
                                }
                            }
                        }],
                        "P27": [{
                            "mainsnak": {
                                "datavalue": {
                                    "type": "wikibase-entityid",
                                    "value": {"id": "Q159"}
                                }
                            }
                        }]
                    },
                    "descriptions": {"ru": {"value": "российский государственный деятель"}}
                }
            }
        }
        mock_response.raise_for_status = Mock()
        
        with patch('backend.services.wikidata_service.requests.get', return_value=mock_response):
            with patch.object(service, '_get_label_for_qid') as mock_get_label:
                def label_side_effect(qid, lang):
                    if qid == "Q11696":
                        return "Президент России"
                    elif qid == "Q159":
                        return "Россия"
                    return None
                
                mock_get_label.side_effect = label_side_effect
                
                result = service.get_entity_info("Q7747", "ru")
                
                assert result is not None
                metadata = result["metadata"]
                assert "positions" in metadata
                assert "country" in metadata or "countries" in metadata

