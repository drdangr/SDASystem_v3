# Troubleshooting Guide

## Проблема: ERR_CONNECTION_REFUSED на localhost:8000

### Решение 1: Проверьте, что сервер запущен

```bash
# Проверьте процессы
ps aux | grep "python.*main.py"

# Проверьте порт
lsof -i:8000

# Запустите сервер
source venv/bin/activate
python main.py
```

### Решение 2: Убедитесь, что порт не занят

```bash
# Освободите порт, если занят
lsof -ti:8000 | xargs kill -9

# Запустите снова
python main.py
```

### Решение 3: Проверьте подключение

```bash
# Проверьте health endpoint
curl http://localhost:8000/api/health

# Проверьте UI endpoint
curl http://localhost:8000/ui
```

### Решение 4: Проверьте логи

Если сервер запущен, но не отвечает, проверьте логи в терминале, где запущен `python main.py`.

### Решение 5: Перезапустите сервер

```bash
# Остановите текущий процесс (Ctrl+C)
# Затем запустите снова
source venv/bin/activate
python main.py
```

## Проверка работы системы

### 1. Проверка базы данных

```bash
psql -U postgres -d sdas_db -c "SELECT COUNT(*) FROM news;"
```

### 2. Проверка API

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/stories
```

### 3. Проверка UI

Откройте в браузере:
- http://localhost:8000/ui
- http://localhost:8000/docs

## Частые проблемы

### Проблема: ModuleNotFoundError: No module named 'psycopg2'

**Решение:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Проблема: PostgreSQL connection failed

**Решение:**
1. Проверьте, что PostgreSQL запущен: `brew services list | grep postgresql`
2. Проверьте .env файл с правильными параметрами
3. Проверьте подключение: `psql -U postgres -d sdas_db`

### Проблема: pgvector extension not found

**Решение:**
```bash
psql -U postgres -d sdas_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

