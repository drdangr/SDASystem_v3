# Генерация мок‑данных (вручную, по необходимости)

По умолчанию SDASystem **не генерирует мок‑данные при запуске**. Это сделано специально, чтобы не затирать рабочие данные в `data/*.json`.

## Что делает генератор
Скрипт генерирует и **перезаписывает** файлы:
- `data/news.json`
- `data/actors.json`
- `data/stories.json`
- `data/domains.json`

## Как запустить

Из корня проекта:

```bash
source venv/bin/activate
python scripts/generate_mock_data.py --force
```

Если нужно писать в другую директорию:

```bash
python scripts/generate_mock_data.py --data-dir /path/to/some/data --force
```

## Безопасность
Без флага `--force` скрипт **откажется** перезаписывать уже существующие файлы.


