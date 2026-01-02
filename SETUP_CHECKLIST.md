# Чеклист настройки SDASystem v3 с PostgreSQL

## ✅ Шаг 1: Установка PostgreSQL + pgvector

Выберите один из вариантов:

### Вариант A: Docker (рекомендуется)
```bash
./scripts/setup_database_docker.sh
```

### Вариант B: Локальная установка
См. [QUICK_START_DATABASE.md](QUICK_START_DATABASE.md) для инструкций по вашей ОС.

**Проверка:**
```bash
psql --version  # или
docker-compose ps  # для Docker
```

## ✅ Шаг 2: Создание .env файла

```bash
cp .env.example .env
```

Отредактируйте `.env` с вашими параметрами подключения к БД.

**Проверка:**
```bash
cat .env | grep POSTGRES
```

## ✅ Шаг 3: Применение схемы БД

Если используете скрипт setup_database.sh, схема применяется автоматически.

Вручную:
```bash
psql -U postgres -d sdas_db -f backend/db/schema.sql
```

Или через Docker:
```bash
docker-compose exec postgres psql -U postgres -d sdas_db -f /path/to/backend/db/schema.sql
```

**Проверка:**
```python
from backend.services.database_manager import DatabaseManager
db = DatabaseManager()
if db.test_connection():
    print("✓ БД настроена")
```

## ✅ Шаг 4: Миграция данных (если есть JSON файлы)

```bash
python scripts/migrate_json_to_db.py
```

**Проверка:**
```python
from backend.services.database_manager import DatabaseManager
db = DatabaseManager()
news_count = len(db.get_all_news())
actors_count = len(db.get_all_actors())
print(f"News: {news_count}, Actors: {actors_count}")
```

## ✅ Шаг 5: Установка Python зависимостей

```bash
pip install -r requirements.txt
```

**Проверка:**
```bash
python -c "import psycopg2; import sqlalchemy; print('✓ Зависимости установлены')"
```

## ✅ Шаг 6: Запуск системы

```bash
python main.py
```

**Проверка:**
- Откройте http://localhost:8000
- Проверьте API: http://localhost:8000/api/health

## Troubleshooting

### Проблема: PostgreSQL не найден
**Решение:** Установите PostgreSQL или используйте Docker

### Проблема: Ошибка подключения к БД
**Решение:** 
- Проверьте параметры в `.env`
- Убедитесь, что PostgreSQL запущен
- Проверьте права доступа пользователя

### Проблема: Расширение pgvector не установлено
**Решение:**
```sql
psql -U postgres -d sdas_db
CREATE EXTENSION vector;
```

### Проблема: БД пустая после миграции
**Решение:**
- Проверьте наличие JSON файлов в `data/`
- Проверьте логи миграции
- Выполните миграцию вручную

## Дополнительные ресурсы

- [Быстрый старт](QUICK_START_DATABASE.md)
- [Детальная установка](docs/database_setup.md)
- [Схема БД](docs/database_schema.md)
- [Миграция данных](docs/DATABASE_MIGRATION.md)

