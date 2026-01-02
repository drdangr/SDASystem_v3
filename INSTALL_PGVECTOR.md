# Установка pgvector для PostgreSQL 14

## Проблема

pgvector установлен через Homebrew, но для PostgreSQL 17/18, а у вас PostgreSQL 14.

## Решение

Выполните следующую команду (потребуется ввести пароль для sudo):

```bash
./scripts/install_pgvector.sh
```

Или вручную:

```bash
cd /tmp
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
export PG_CONFIG=/opt/homebrew/opt/postgresql@14/bin/pg_config
make
sudo make install
```

## После установки

1. Создайте расширение в БД:
```bash
psql -U postgres -d sdas_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

2. Примените схему:
```bash
psql -U postgres -d sdas_db -f backend/db/schema.sql
```

3. Проверьте подключение:
```bash
python scripts/migrate_json_to_db.py
```

