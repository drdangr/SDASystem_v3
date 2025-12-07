#!/usr/bin/env python3
"""
Скрипт для перезагрузки данных и извлечения акторов из новой русскоязычной новости
"""
import sys
import json
import os
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Импортируем напрямую, так как load_data вызывается при старте сервера
from backend.services.graph_manager import GraphManager
from backend.services.embedding_service import EmbeddingService
from backend.services.event_extraction_service import EventExtractionService
from backend.services.llm_service import LLMService
from backend.services.actors_extraction_service import ActorsExtractionService
from backend.models.entities import News, Actor, Story
from datetime import datetime
import os

def reload_data():
    """Перезагрузить данные из файлов"""
    print("=" * 60)
    print("Перезагрузка данных из файлов...")
    print("=" * 60)
    
    # Создаем сервисы
    graph_manager = GraphManager()
    embedding_service = EmbeddingService(use_mock=True)
    event_service = EventExtractionService()
    
    data_dir = "data"
    
    # Загружаем акторов
    if os.path.exists(f"{data_dir}/actors.json"):
        with open(f"{data_dir}/actors.json", 'r', encoding='utf-8') as f:
            actors_data = json.load(f)
            for item in actors_data:
                actor = Actor(**item)
                graph_manager.add_actor(actor)
            print(f"✓ Загружено {len(actors_data)} акторов")
    
    # Загружаем новости
    if os.path.exists(f"{data_dir}/news.json"):
        with open(f"{data_dir}/news.json", 'r', encoding='utf-8') as f:
            news_data = json.load(f)
            for item in news_data:
                if 'published_at' in item and item['published_at']:
                    item['published_at'] = datetime.fromisoformat(item['published_at'])
                news = News(**item)
                if not news.embedding:
                    news.embedding = embedding_service.encode(news.full_text or news.summary)[0].tolist()
                graph_manager.add_news(news)
            print(f"✓ Загружено {len(news_data)} новостей")
    
    # Загружаем истории
    if os.path.exists(f"{data_dir}/stories.json"):
        with open(f"{data_dir}/stories.json", 'r', encoding='utf-8') as f:
            stories_data = json.load(f)
            for item in stories_data:
                if 'first_seen' in item and item['first_seen']:
                    item['first_seen'] = datetime.fromisoformat(item['first_seen'])
                if 'last_activity' in item and item['last_activity']:
                    item['last_activity'] = datetime.fromisoformat(item['last_activity'])
                if not item.get('summary'):
                    item['summary'] = f"Auto summary for {item.get('title', 'Story')}"
                if not item.get('bullets'):
                    item['bullets'] = [f"Key point for {item.get('title', 'story')}"]
                if not item.get('domains'):
                    item['domains'] = []
                if not item.get('top_actors'):
                    item['top_actors'] = []
                story = Story(**item)
                graph_manager.add_story(story)
            print(f"✓ Загружено {len(stories_data)} историй")
    
    # Вычисляем схожести
    print("Вычисление схожести новостей...")
    graph_manager.compute_news_similarities(threshold=0.6)
    
    # Проверяем новую новость
    news_id = "news_6d39500d2052"
    if news_id in graph_manager.news:
        news = graph_manager.news[news_id]
        print(f"\n✓ Новая новость найдена: {news.title[:60]}...")
        print(f"  Story ID: {news.story_id}")
        print(f"  Акторов: {len(news.mentioned_actors)}")
        return graph_manager, news_id
    else:
        print(f"\n✗ Новость {news_id} не найдена!")
        return None, None

def extract_actors_for_news(graph_manager, news_id: str):
    """Извлечь акторов из новости"""
    news = graph_manager.news.get(news_id)
    if not news:
        print(f"\n✗ Новость {news_id} не найдена в графе!")
        return False
    
    print("\n" + "=" * 60)
    print(f"Извлечение акторов из новости {news_id}...")
    print(f"Заголовок: {news.title[:60]}...")
    print("=" * 60)
    
    # Создаем сервис извлечения акторов
    from dotenv import load_dotenv
    load_dotenv()
    
    llm_service = LLMService(api_key=os.getenv("GEMINI_API_KEY"))
    spacy_model = os.getenv("SPACY_MODEL", "en_core_web_sm")
    
    print(f"Используется spaCy модель: {spacy_model}")
    if spacy_model == "en_core_web_sm":
        print("⚠️  Внимание: английская модель может плохо работать с русским текстом!")
        print("   Рекомендуется установить русскую модель: python -m spacy download ru_core_news_md")
        print("   Или использовать LLM для извлечения акторов.")
    
    try:
        actors_service = ActorsExtractionService(
            graph_manager,
            llm_service,
            data_dir="data",
            use_spacy=True,
            spacy_model=spacy_model,
        )
        
        # Извлекаем акторов (метод принимает объект News)
        extracted, actor_ids = actors_service.extract_for_news(news, low_conf_threshold=0.75)
        
        # Сохраняем изменения в файлы
        actors_service._save_actors()
        actors_service._save_news()
        
        print(f"\n✓ Извлечено акторов: {len(actor_ids)}")
        print(f"  Извлеченных сущностей: {len(extracted)}")
        print(f"  Actor IDs: {actor_ids}")
        
        # Показываем информацию об акторах
        for actor_id in actor_ids:
            actor = graph_manager.actors.get(actor_id)
            if actor:
                aliases_str = ", ".join([a.get("name", "") for a in actor.aliases[:3]])
                print(f"    - {actor.canonical_name} ({actor.actor_type})")
                if aliases_str:
                    print(f"      Алиасы: {aliases_str}")
        
        return True
    except Exception as e:
        print(f"\n✗ Ошибка при извлечении акторов: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Основная функция"""
    print("\n" + "=" * 60)
    print("Перезагрузка данных и извлечение акторов")
    print("=" * 60 + "\n")
    
    # Перезагружаем данные
    graph_manager, news_id = reload_data()
    
    if not news_id or not graph_manager:
        print("\n✗ Не удалось найти новую новость. Проверьте файл data/news.json")
        return 1
    
    # Извлекаем акторов
    success = extract_actors_for_news(graph_manager, news_id)
    
    if success:
        print("\n" + "=" * 60)
        print("✓ Готово! Теперь перезагрузите страницу в браузере")
        print("=" * 60)
        return 0
    else:
        print("\n✗ Произошла ошибка при извлечении акторов")
        return 1

if __name__ == "__main__":
    sys.exit(main())

