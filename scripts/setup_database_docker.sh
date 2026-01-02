#!/bin/bash
# Скрипт для настройки базы данных через Docker

set -e

echo "=========================================="
echo "SDASystem Database Setup (Docker)"
echo "=========================================="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не найден"
    echo "Установите Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Проверка docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose не найден"
    echo "Установите docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "Запуск PostgreSQL + pgvector в Docker..."
docker-compose up -d

echo "Ожидание готовности PostgreSQL..."
sleep 5

# Проверка здоровья
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U postgres &> /dev/null; then
        echo "✓ PostgreSQL готов"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL не запустился за 30 секунд"
        exit 1
    fi
    sleep 1
done

# Применение схемы
SCHEMA_FILE="backend/db/schema.sql"
if [ -f "$SCHEMA_FILE" ]; then
    echo "Применение схемы БД..."
    docker-compose exec -T postgres psql -U postgres -d sdas_db -f /dev/stdin < "$SCHEMA_FILE"
    echo "✓ Схема применена"
else
    echo "⚠ Файл схемы не найден: $SCHEMA_FILE"
fi

echo ""
echo "=========================================="
echo "✓ База данных настроена!"
echo "=========================================="
echo ""
echo "Параметры подключения (для .env):"
echo "  POSTGRES_DB=sdas_db"
echo "  POSTGRES_USER=postgres"
echo "  POSTGRES_PASSWORD=postgres"
echo "  POSTGRES_HOST=localhost"
echo "  POSTGRES_PORT=5432"
echo ""
echo "Следующие шаги:"
echo "1. Создайте .env файл с параметрами выше"
echo "2. Выполните миграцию: python scripts/migrate_json_to_db.py"
echo "3. Запустите систему: python main.py"
echo ""
echo "Для остановки: docker-compose down"
echo "Для просмотра логов: docker-compose logs -f"

