"""
Скрипт для создания бэкапа ожидаемых акторов для каждой новости.
Используется для тестирования LLM-сервиса извлечения акторов.
"""
import json
from pathlib import Path
from typing import Dict, List

# Пути к данным
PROJECT_ROOT = Path(__file__).parent.parent
NEWS_FILE = PROJECT_ROOT / "data" / "news.json"
ACTORS_FILE = PROJECT_ROOT / "data" / "actors.json"
BACKUP_DIR = PROJECT_ROOT / "data" / "backup" / "actors_test"


def load_json(file_path: Path) -> List[Dict]:
    """Загрузить JSON файл"""
    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_actors_index(actors: List[Dict]) -> Dict[str, Dict]:
    """Создать индекс акторов по ID"""
    index = {}
    for actor in actors:
        index[actor["id"]] = actor
    return index


def normalize_name(name: str) -> str:
    """Нормализовать имя для сравнения"""
    return name.lower().strip()


def create_expected_actors(news: Dict, actors_index: Dict[str, Dict]) -> List[Dict]:
    """
    Создать ожидаемый список акторов для новости.
    Включает канонические имена, типы, алиасы и все возможные варианты упоминаний.
    """
    expected = []
    mentioned_actor_ids = news.get("mentioned_actors", [])
    
    for actor_id in mentioned_actor_ids:
        if actor_id not in actors_index:
            continue
        
        actor = actors_index[actor_id]
        
        # Собираем все возможные упоминания
        mentions = set()
        
        # Каноническое имя
        canonical_name = actor.get("canonical_name", "")
        if canonical_name:
            mentions.add(canonical_name)
            mentions.add(normalize_name(canonical_name))
        
        # Все алиасы
        aliases = actor.get("aliases", [])
        alias_names = []
        for alias in aliases:
            alias_name = alias.get("name", "")
            if alias_name:
                mentions.add(alias_name)
                mentions.add(normalize_name(alias_name))
                alias_names.append(alias_name)
        
        # Создаем ожидаемый объект актора
        expected_actor = {
            "id": actor_id,
            "canonical_name": canonical_name,
            "actor_type": actor.get("actor_type", "organization"),
            "aliases": alias_names,
            "all_mentions": list(mentions),  # Все возможные варианты упоминания
            "normalized_names": [normalize_name(m) for m in mentions if m]
        }
        
        expected.append(expected_actor)
    
    return expected


def main():
    """Основная функция: создать бэкапы для всех новостей"""
    print("Загрузка данных...")
    news_list = load_json(NEWS_FILE)
    actors_list = load_json(ACTORS_FILE)
    
    print(f"Загружено новостей: {len(news_list)}")
    print(f"Загружено акторов: {len(actors_list)}")
    
    # Создать индекс акторов
    actors_index = create_actors_index(actors_list)
    
    # Создать директорию для бэкапов
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Создать метаданные для всего набора
    metadata = {
        "total_news": len(news_list),
        "total_actors": len(actors_list),
        "news_mapping": {}
    }
    
    # Обработать каждую новость
    processed_count = 0
    for news in news_list:
        news_id = news.get("id")
        if not news_id:
            continue
        
        # Создать ожидаемые акторы
        expected_actors = create_expected_actors(news, actors_index)
        
        # Сохранить в файл
        backup_data = {
            "news_id": news_id,
            "news_title": news.get("title", ""),
            "news_text": f"{news.get('title', '')}\n{news.get('summary', '')}\n{news.get('full_text', '')}",
            "expected_actors": expected_actors,
            "original_mentioned_actors": news.get("mentioned_actors", [])
        }
        
        backup_file = BACKUP_DIR / f"{news_id}.json"
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        metadata["news_mapping"][news_id] = {
            "title": news.get("title", ""),
            "expected_actors_count": len(expected_actors)
        }
        
        processed_count += 1
    
    # Сохранить метаданные
    metadata_file = BACKUP_DIR / "_metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"\nГотово! Обработано новостей: {processed_count}")
    print(f"Бэкапы сохранены в: {BACKUP_DIR}")
    print(f"Метаданные: {metadata_file}")


if __name__ == "__main__":
    main()

