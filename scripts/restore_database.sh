#!/bin/bash
# Restore script for PostgreSQL database
# Usage: ./scripts/restore_database.sh <backup_file>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

DB_NAME=${POSTGRES_DB:-sdas_db}
DB_USER=${POSTGRES_USER:-postgres}
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}

echo "WARNING: This will replace all data in database ${DB_NAME}"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

echo "Restoring database ${DB_NAME} from ${BACKUP_FILE}..."

# Drop and recreate database
PGPASSWORD=${POSTGRES_PASSWORD} psql \
    -h ${DB_HOST} \
    -p ${DB_PORT} \
    -U ${DB_USER} \
    -d postgres \
    -c "DROP DATABASE IF EXISTS ${DB_NAME};"

PGPASSWORD=${POSTGRES_PASSWORD} psql \
    -h ${DB_HOST} \
    -p ${DB_PORT} \
    -U ${DB_USER} \
    -d postgres \
    -c "CREATE DATABASE ${DB_NAME};"

# Restore from backup
PGPASSWORD=${POSTGRES_PASSWORD} pg_restore \
    -h ${DB_HOST} \
    -p ${DB_PORT} \
    -U ${DB_USER} \
    -d ${DB_NAME} \
    -v \
    ${BACKUP_FILE}

if [ $? -eq 0 ]; then
    echo "✓ Restore completed successfully"
    
    # Recreate pgvector extension
    PGPASSWORD=${POSTGRES_PASSWORD} psql \
        -h ${DB_HOST} \
        -p ${DB_PORT} \
        -U ${DB_USER} \
        -d ${DB_NAME} \
        -c "CREATE EXTENSION IF NOT EXISTS vector;"
    
    echo "✓ Database restored and pgvector extension enabled"
else
    echo "✗ Restore failed"
    exit 1
fi

