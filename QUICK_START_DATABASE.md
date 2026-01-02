# Быстрый старт: Настройка базы данных

## Вариант 1: Docker (рекомендуется)

Если у вас установлен Docker:

```bash
# 1. Запустить PostgreSQL + pgvector
./scripts/setup_database_docker.sh

# 2. Создать .env файл
cp .env.example .env
# Отредактируйте .env при необходимости

# 3. Выполнить миграцию данных
python scripts/migrate_json_to_db.py

# 4. Запустить систему
python main.py
```

## Вариант 2: Локальная установка PostgreSQL

### macOS (Homebrew)

```bash
# 1. Установить PostgreSQL
brew install postgresql@14
brew services start postgresql@14

# 2. Установить pgvector
brew install pgvector

# 3. Настроить БД
./scripts/setup_database.sh

# 4. Создать .env файл
cp .env.example .env
# Отредактируйте .env при необходимости

# 5. Выполнить миграцию
python scripts/migrate_json_to_db.py

# 6. Запустить систему
python main.py
```

### Ubuntu/Debian

```bash
# 1. Установить PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# 2. Установить pgvector (из исходников)
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# 3. Настроить БД
./scripts/setup_database.sh

# 4. Создать .env файл
cp .env.example .env
# Отредактируйте .env при необходимости

# 5. Выполнить миграцию
python scripts/migrate_json_to_db.py

# 6. Запустить систему
python main.py
```

## Создание .env файла

Создайте файл `.env` в корне проекта со следующим содержимым:

```env
# PostgreSQL Database Configuration
POSTGRES_DB=sdas_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Gemini LLM Configuration (если используется)
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMP=0.3
GEMINI_TOP_P=0.9
GEMINI_TOP_K=40
GEMINI_MAX_TOKENS=1024
GEMINI_TIMEOUT=15

# LLM Services Config
LLM_SERVICES_CONFIG=config/llm_services.json
```

## Проверка установки

После настройки проверьте подключение:

```python
from backend.services.database_manager import DatabaseManager

db = DatabaseManager()
if db.test_connection():
    print("✓ Подключение к БД успешно!")
else:
    print("✗ Ошибка подключения к БД")
```

## Troubleshooting

### Ошибка подключения
- Проверьте, что PostgreSQL запущен: `pg_isready` или `docker-compose ps`
- Проверьте параметры в `.env` файле
- Проверьте права доступа пользователя

### Ошибка расширения pgvector
```sql
psql -U postgres -d sdas_db
CREATE EXTENSION vector;
```

### Docker контейнер не запускается
```bash
docker-compose logs postgres
docker-compose down
docker-compose up -d
```

## Дополнительная информация

- [Детальная инструкция по установке](docs/database_setup.md)
- [Схема базы данных](docs/database_schema.md)
- [Руководство по миграции](docs/DATABASE_MIGRATION.md)

