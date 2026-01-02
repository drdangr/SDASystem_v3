#!/bin/bash
# Скрипт для настройки базы данных PostgreSQL + pgvector

set -e

echo "=========================================="
echo "SDASystem Database Setup"
echo "=========================================="

# Проверка наличия PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL не найден в PATH"
    echo ""
    echo "Варианты установки:"
    echo "1. Использовать Docker (рекомендуется):"
    echo "   docker-compose up -d"
    echo ""
    echo "2. Установить вручную:"
    echo "   macOS: brew install postgresql@14"
    echo "   Ubuntu: sudo apt install postgresql postgresql-contrib"
    echo ""
    echo "См. docs/database_setup.md для детальных инструкций"
    exit 1
fi

# Параметры подключения
DB_NAME="${POSTGRES_DB:-sdas_db}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "Параметры подключения:"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo ""

# Проверка подключения
echo "Проверка подключения к PostgreSQL..."
export PGPASSWORD="$DB_PASSWORD"
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "SELECT 1" &> /dev/null; then
    echo "❌ Не удалось подключиться к PostgreSQL"
    echo "Проверьте параметры подключения в .env файле"
    exit 1
fi
echo "✓ Подключение успешно"
echo ""

# Создание базы данных
echo "Создание базы данных $DB_NAME..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres <<EOF
SELECT 'CREATE DATABASE $DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec
EOF
echo "✓ База данных создана или уже существует"
echo ""

# Установка расширения pgvector
echo "Установка расширения pgvector..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
CREATE EXTENSION IF NOT EXISTS vector;
EOF
echo "✓ Расширение pgvector установлено"
echo ""

# Применение схемы
SCHEMA_FILE="backend/db/schema.sql"
if [ -f "$SCHEMA_FILE" ]; then
    echo "Применение схемы БД из $SCHEMA_FILE..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_FILE"
    echo "✓ Схема применена"
else
    echo "⚠ Файл схемы не найден: $SCHEMA_FILE"
fi
echo ""

echo "=========================================="
echo "✓ Настройка базы данных завершена!"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo "1. Выполните миграцию данных: python scripts/migrate_json_to_db.py"
echo "2. Запустите систему: python main.py"

