#!/bin/bash
# Backup script for PostgreSQL database
# Usage: ./scripts/backup_database.sh [output_file]

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

DB_NAME=${POSTGRES_DB:-sdas_db}
DB_USER=${POSTGRES_USER:-postgres}
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}

# Output file
if [ -z "$1" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    OUTPUT_FILE="backups/sdas_db_backup_${TIMESTAMP}.sql"
else
    OUTPUT_FILE="$1"
fi

# Create backups directory if it doesn't exist
mkdir -p backups

echo "Backing up database ${DB_NAME} to ${OUTPUT_FILE}..."

# Perform backup
PGPASSWORD=${POSTGRES_PASSWORD} pg_dump \
    -h ${DB_HOST} \
    -p ${DB_PORT} \
    -U ${DB_USER} \
    -d ${DB_NAME} \
    -F c \
    -f ${OUTPUT_FILE}

if [ $? -eq 0 ]; then
    echo "✓ Backup completed successfully: ${OUTPUT_FILE}"
    echo "Backup size: $(du -h ${OUTPUT_FILE} | cut -f1)"
else
    echo "✗ Backup failed"
    exit 1
fi

