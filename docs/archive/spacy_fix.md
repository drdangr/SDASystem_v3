# Решение проблемы с spaCy

## Проблема

spaCy был установлен, но модели не были установлены. При попытке использовать `spacy download` возникали ошибки 404.

## Причина

Команда `python -m spacy download <model>` не работала из-за проблем с доступом к репозиторию моделей или неправильного формата команды.

## Решение

Модель была установлена напрямую через pip:

```bash
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
```

## Установленные модели

- ✅ `en_core_web_sm` (3.7.1) - английская модель с NER компонентом

## Проверка работы

```python
import spacy

nlp = spacy.load('en_core_web_sm')
doc = nlp('Vladimir Putin visited the United States.')

for ent in doc.ents:
    print(f'{ent.text} ({ent.label_})')
# Вывод:
# Vladimir Putin (PERSON)
# the United States (GPE)
```

## Обновление кода

По умолчанию используется `en_core_web_sm` вместо `ru_core_news_lg` в `HybridNERService`, так как:
1. Английская модель более доступна
2. Большинство тестовых данных на английском
3. Можно легко переключиться на русскую модель при необходимости

## Установка других моделей

### Английская (большая):
```bash
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl
```

### Русская:
```bash
pip install https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.7.0/ru_core_news_sm-3.7.0-py3-none-any.whl
```

Или найти актуальные версии на: https://github.com/explosion/spacy-models/releases

## Альтернативный способ (если pip не работает)

Можно попробовать через команду spacy (иногда работает после обновления):

```bash
python -m spacy download en_core_web_sm
```

Но если это не работает, используйте прямой pip установку как выше.

## Текущий статус

✅ spaCy модель установлена и работает
✅ HybridNERService использует spaCy для первичного извлечения
✅ Гибридный подход полностью функционален

