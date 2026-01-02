#!/bin/bash
# Установка pgvector для PostgreSQL 14

set -e

echo "=========================================="
echo "Установка pgvector для PostgreSQL 14"
echo "=========================================="

PG_CONFIG="/opt/homebrew/opt/postgresql@14/bin/pg_config"
if [ ! -f "$PG_CONFIG" ]; then
    echo "❌ pg_config не найден: $PG_CONFIG"
    exit 1
fi

# Клонирование и компиляция
TMP_DIR="/tmp/pgvector_install_$$"
mkdir -p "$TMP_DIR"
cd "$TMP_DIR"

echo "Клонирование pgvector..."
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector

echo "Компиляция pgvector..."
export PG_CONFIG
make

echo "Установка pgvector (требуется sudo)..."
sudo make install

echo "Очистка..."
cd /
rm -rf "$TMP_DIR"

echo ""
echo "=========================================="
echo "✓ pgvector установлен!"
echo "=========================================="
echo ""
echo "Теперь выполните:"
echo "  psql -U postgres -d sdas_db -c 'CREATE EXTENSION vector;'"
echo "  psql -U postgres -d sdas_db -f backend/db/schema.sql"
