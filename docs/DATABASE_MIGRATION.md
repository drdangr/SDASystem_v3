# Миграция на PostgreSQL + pgvector

## Краткое описание

Система мигрирована с хранения данных в JSON файлах на PostgreSQL + pgvector. Все вычислимые данные (news, actors, stories, events, domains, relations) теперь хранятся в БД.

## Что изменилось

### Архитектура
- **DatabaseManager** (`backend/services/database_manager.py`) - новый слой доступа к БД
- **GraphManager** - рефакторен для работы с БД вместо in-memory словарей
- **Сервисы** - обновлены для работы через GraphManager (который использует БД)

### Хранение данных
- **Раньше**: `data/*.json` файлы
- **Теперь**: PostgreSQL таблицы с векторными индексами

### Векторный поиск
- **Раньше**: sklearn `cosine_similarity` (in-memory)
- **Теперь**: pgvector `<=>` оператор (в БД, оптимизировано)

## Быстрый старт

### 1. Установка PostgreSQL + pgvector

См. [docs/database_setup.md](database_setup.md) для детальных инструкций.

**Минимальные шаги:**
```bash
# Установить PostgreSQL
brew install postgresql@14  # macOS
# или
sudo apt install postgresql postgresql-contrib  # Ubuntu

# Создать БД
psql -U postgres
CREATE DATABASE sdas_db;
CREATE EXTENSION vector;
\q

# Применить схему
psql -U postgres -d sdas_db -f backend/db/schema.sql
```

### 2. Настройка переменных окружения

Создайте `.env` файл:
```env
POSTGRES_DB=sdas_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### 3. Миграция данных

Если у вас есть данные в JSON:
```bash
python scripts/migrate_json_to_db.py
```

### 4. Проверка работы

Запустите тесты для проверки корректности работы БД:

```bash
source venv/bin/activate
python -m pytest tests/test_database_manager.py -v
```

Все 36 тестов должны пройти успешно. Подробный отчет: [docs/database_tests_report.md](database_tests_report.md)

### 5. Запуск системы

```bash
python main.py
```

Система автоматически:
- Подключится к БД
- Загрузит данные из БД (или JSON, если БД пустая)
- Построит графы для визуализации

## Проверка работы

### Проверка подключения
```python
from backend.services.database_manager import DatabaseManager

db = DatabaseManager()
with db.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM news")
        print(f"News count: {cur.fetchone()[0]}")
```

### Запуск тестов
```bash
# Активировать виртуальное окружение
source venv/bin/activate

# Запустить все тесты DatabaseManager
python -m pytest tests/test_database_manager.py -v

# Все 36 тестов должны пройти успешно
# Покрытие: CRUD операции, связи, векторный поиск, транзакции, интеграционные сценарии
```

Подробный отчет о тестировании: [docs/database_tests_report.md](database_tests_report.md)

## Обратная совместимость

Система поддерживает обратную совместимость:
- Если БД пустая, загружает из JSON (режим миграции)
- GraphManager предоставляет свойства `.news`, `.actors`, `.stories` для совместимости
- API endpoints работают без изменений

## Производительность

### Векторный поиск
- **pgvector**: O(log n) с индексом ivfflat
- **sklearn**: O(n²) для всех пар
- **Улучшение**: в 10-100 раз быстрее на больших объемах (>1000 новостей)

### Загрузка данных
- **БД**: быстрая загрузка только нужных данных
- **JSON**: загрузка всех данных в память
- **Улучшение**: меньше использование памяти, быстрее старт

## Troubleshooting

### Ошибка подключения
```
Error creating connection pool: ...
```
**Решение**: Проверьте переменные окружения и что PostgreSQL запущен.

### Ошибка расширения pgvector
```
ERROR: extension "vector" does not exist
```
**Решение**: Установите pgvector и выполните `CREATE EXTENSION vector;`

### Пустая БД при запуске
Система автоматически загрузит данные из JSON, если БД пустая. После этого выполните миграцию:
```bash
python scripts/migrate_json_to_db.py
```

## Дополнительная информация

- [Схема БД](database_schema.md)
- [Инструкции по установке](database_setup.md)
- [Архитектура бэкенда](architecture/backend.md)

