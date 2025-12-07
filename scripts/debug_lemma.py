
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.getcwd())

from backend.services.actor_canonicalization_service import ActorCanonicalizationService
from backend.services.ner_spacy_service import get_model_for_language, check_model_available
import spacy

def test_lemmatization():
    print("--- Testing Lemmatization ---")
    
    # Check available models
    ru_model = get_model_for_language('ru', prefer_large=False)
    print(f"Target Russian model: {ru_model}")
    print(f"Model available: {check_model_available(ru_model)}")
    
    service = ActorCanonicalizationService(use_wikidata=False, use_lemmatization=True)
    
    test_cases = [
        "Зеленского",
        "Джо Байдена",
        "Владимира Путина",
        "Россией",
        "Украиной"
    ]
    
    for text in test_cases:
        lemma = service._lemmatize_russian(text)
        print(f"Original: '{text}' -> Lemma: '{lemma}'")
        
        # Test normalization (capitalization)
        norm = service._normalize_russian_name(text)
        print(f"Normalized: '{norm}'")

if __name__ == "__main__":
    test_lemmatization()

