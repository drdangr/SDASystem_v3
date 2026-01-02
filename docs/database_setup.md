# Database Setup Guide

Инструкция по установке и настройке PostgreSQL + pgvector для SDASystem v3.

## Тестирование

После настройки БД рекомендуется запустить тесты для проверки корректности работы:

```bash
# Активировать виртуальное окружение
source venv/bin/activate

# Запустить тесты DatabaseManager
python -m pytest tests/test_database_manager.py -v

# Все 36 тестов должны пройти успешно
```

Подробный отчет о тестировании: [docs/database_tests_report.md](../database_tests_report.md)

---

## Требования

- PostgreSQL 12 или выше
- Python 3.9+
- Доступ к интернету для установки расширения pgvector

## Установка PostgreSQL

### macOS (Homebrew)
```bash
brew install postgresql@14
brew services start postgresql@14
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### Docker
```bash
docker run --name sdas-postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=sdas_db \
  -p 5432:5432 \
  -d pgvector/pgvector:pg14
```

## Установка pgvector

### macOS (Homebrew)
```bash
brew install pgvector
```

### Из исходников
```bash
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### Docker
Используйте образ `pgvector/pgvector:pg14` (см. выше).

## Настройка базы данных

1. Создайте базу данных:
```bash
psql -U postgres
CREATE DATABASE sdas_db;
\q
```

2. Подключитесь к базе данных и установите расширение:
```bash
psql -U postgres -d sdas_db
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

3. Примените схему:
```bash
psql -U postgres -d sdas_db -f backend/db/schema.sql
```

## Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
# PostgreSQL connection
POSTGRES_DB=sdas_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Или установите переменные окружения:

```bash
export POSTGRES_DB=sdas_db
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=yourpassword
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
```

## Миграция данных

После настройки БД выполните миграцию данных из JSON:

```bash
python scripts/migrate_json_to_db.py
```

Скрипт:
- Читает данные из `data/*.json`
- Мигрирует в PostgreSQL
- Вычисляет similarities между новостями
- Валидирует миграцию

## Проверка установки

Проверьте подключение:

```python
from backend.services.database_manager import DatabaseManager

db = DatabaseManager()
with db.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        print(cur.fetchone())
```

## Тестирование

Запустите тесты:

```bash
# Установите тестовую БД
export TEST_POSTGRES_DB=sdas_test_db
export TEST_POSTGRES_USER=postgres
export TEST_POSTGRES_PASSWORD=yourpassword

# Запустите тесты
pytest tests/test_database_manager.py -v
```

## Troubleshooting

### Ошибка подключения
- Проверьте, что PostgreSQL запущен: `pg_isready`
- Проверьте переменные окружения
- Проверьте права доступа пользователя

### Ошибка расширения pgvector
- Убедитесь, что расширение установлено: `psql -d sdas_db -c "CREATE EXTENSION vector;"`
- Проверьте версию PostgreSQL: `psql -c "SELECT version();"`

### Ошибка векторного индекса
- Убедитесь, что в таблице `news` есть данные с embeddings
- Проверьте размер вектора (должен быть 384 для MiniLM)

## Backup и Restore

### Backup
```bash
pg_dump -U postgres -d sdas_db > backup.sql
```

### Restore
```bash
psql -U postgres -d sdas_db < backup.sql
```

## Производительность

Для оптимизации производительности:

1. Настройте `shared_buffers` в `postgresql.conf`
2. Используйте `hnsw` индекс вместо `ivfflat` для больших объемов (>1M векторов)
3. Регулярно выполняйте `VACUUM ANALYZE`

## Дополнительные ресурсы

- [pgvector документация](https://github.com/pgvector/pgvector)
- [PostgreSQL документация](https://www.postgresql.org/docs/)

