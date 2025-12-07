#!/usr/bin/env python3
"""
Детальный анализ извлечения акторов для новости про Tesla.
"""
import json
import spacy
from pathlib import Path

text = """Tesla Opens New Gigafactory in Texas
Tesla announced the official opening of its latest Gigafactory in Austin, Texas, expanding US electric vehicle production capacity.
Tesla CEO Elon Musk celebrated the grand opening of the company's newest Gigafactory in Austin, Texas. The facility will produce the Cybertruck and Model Y vehicles, significantly boosting Tesla's manufacturing capacity in the United States. The $1.1 billion investment is expected to create thousands of jobs in the region."""

print("="*80)
print("ДЕТАЛЬНЫЙ АНАЛИЗ НОВОСТИ ПРО TESLA")
print("="*80)
print()

# 1. Что ожидается в бэкапе
print("1. ОЖИДАЕМЫЕ АКТОРЫ (из бэкапа)")
print("-"*80)
backup_file = Path("data/backup/actors_test/news_tesla_ev_001.json")
if backup_file.exists():
    with open(backup_file, 'r') as f:
        backup = json.load(f)
    expected = backup.get('expected_actors', [])
    print(f"Ожидается: {len(expected)} акторов")
    for actor in expected:
        print(f"  ✓ {actor['canonical_name']} ({actor['actor_type']})")
        if actor.get('aliases'):
            print(f"    Алиасы: {', '.join(actor['aliases'])}")
else:
    print("Бэкап не найден")
print()

# 2. Что находит spaCy
print("2. ЧТО НАХОДИТ SPACY")
print("-"*80)
nlp = spacy.load('en_core_web_sm')
doc = nlp(text)

entities_by_type = {}
for ent in doc.ents:
    label = ent.label_
    if label not in entities_by_type:
        entities_by_type[label] = []
    entities_by_type[label].append(ent.text)

print(f"Всего найдено: {len(doc.ents)} сущностей")
print()

for label, entities in sorted(entities_by_type.items()):
    print(f"{label}:")
    for entity in set(entities):  # Убрать дубликаты
        print(f"  - {entity}")

print()

# 3. Что пользователь ожидает
print("3. ЧТО ПОЛЬЗОВАТЕЛЬ ОЖИДАЕТ")
print("-"*80)
expected_by_user = {
    "Tesla": "company",
    "Elon Musk": "person (CEO Tesla)",
    "Gigafactory": "facility",
    "Austin": "location",
    "Texas": "location",
    "United States": "country",
    "Cybertruck": "product",
    "Model Y": "product"
}

print("Акторы, которые пользователь ожидает увидеть:")
for name, desc in expected_by_user.items():
    found_in_spacy = any(name.lower() in e.text.lower() or e.text.lower() in name.lower() 
                        for e in doc.ents)
    status = "✓ найдено" if found_in_spacy else "✗ не найдено"
    print(f"  {status:12} {name:20} ({desc})")

print()

# 4. Сравнение
print("4. СРАВНЕНИЕ")
print("-"*80)
print()
print("В бэкапе ожидается: 2 актора")
print("  - Tesla")
print("  - United States")
print()
print("Пользователь ожидает: 8+ акторов")
print("  - Tesla (компания)")
print("  - Elon Musk (персона)")
print("  - Gigafactory (объект)")
print("  - Austin, Texas (локации)")
print("  - United States (страна)")
print("  - Cybertruck, Model Y (продукты)")
print()
print("spaCy находит: 9 сущностей")
print("  - Tesla (ORG) ✓")
print("  - Elon Musk (PERSON) ✓")
print("  - Gigafactory (GPE)")
print("  - Austin, Texas (GPE) ✓")
print("  - United States (GPE) ✓")
print("  - Cybertruck, Model Y (неправильно как PERSON)")
print()
print("ПРОБЛЕМЫ:")
print("  1. LLM возвращает пустой ответ - нужно проверить API")
print("  2. Бэкап неполный - не включает все акторы из текста")
print("  3. spaCy правильно находит сущности, но классификация не идеальна")
print()
print("="*80)

