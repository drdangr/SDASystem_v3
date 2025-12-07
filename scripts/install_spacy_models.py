#!/usr/bin/env python3
"""
Скрипт для установки недостающих моделей spaCy.
Проверяет установленные модели и предлагает установить недостающие.
"""
import subprocess
import sys
import os

# Модели для установки
REQUIRED_MODELS = {
    'en': ['en_core_web_sm', 'en_core_web_lg'],
    'ru': ['ru_core_news_sm', 'ru_core_news_md', 'ru_core_news_lg']
}

def check_model_installed(model_name: str) -> bool:
    """Проверить, установлена ли модель"""
    try:
        import spacy
        try:
            spacy.load(model_name)
            return True
        except (OSError, IOError):
            return False
    except ImportError:
        print("⚠️  spaCy не установлен!")
        return False

def install_model(model_name: str) -> bool:
    """Установить модель spaCy"""
    print(f"📦 Установка модели {model_name}...")
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'spacy', 'download', model_name],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ Модель {model_name} успешно установлена")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при установке {model_name}: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def main():
    """Основная функция"""
    print("=" * 80)
    print("ПРОВЕРКА И УСТАНОВКА МОДЕЛЕЙ SPACY")
    print("=" * 80)
    print()
    
    # Проверяем установку spaCy
    try:
        import spacy
        print(f"✅ spaCy установлен (версия: {spacy.__version__})")
    except ImportError:
        print("❌ spaCy не установлен!")
        print("   Установите: pip install spacy")
        return 1
    
    print()
    print("Проверка установленных моделей:")
    print("-" * 80)
    
    installed = {}
    missing = {}
    
    for lang, models in REQUIRED_MODELS.items():
        installed[lang] = []
        missing[lang] = []
        
        for model in models:
            if check_model_installed(model):
                installed[lang].append(model)
                print(f"✅ {model:30} - установлена")
            else:
                missing[lang].append(model)
                print(f"❌ {model:30} - отсутствует")
    
    print()
    print("=" * 80)
    
    # Если все модели установлены
    if not any(missing.values()):
        print("✅ Все модели установлены!")
        return 0
    
    # Предлагаем установить недостающие
    print("Недостающие модели:")
    for lang, models in missing.items():
        if models:
            print(f"\n{lang.upper()}:")
            for model in models:
                print(f"  - {model}")
    
    print()
    response = input("Установить недостающие модели? (y/n): ").strip().lower()
    
    if response not in ['y', 'yes', 'да', 'д']:
        print("Установка отменена.")
        return 0
    
    print()
    print("=" * 80)
    print("УСТАНОВКА МОДЕЛЕЙ")
    print("=" * 80)
    print()
    
    success_count = 0
    fail_count = 0
    
    for lang, models in missing.items():
        if not models:
            continue
        
        print(f"\nУстановка моделей для {lang.upper()}:")
        print("-" * 80)
        
        for model in models:
            if install_model(model):
                success_count += 1
            else:
                fail_count += 1
    
    print()
    print("=" * 80)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 80)
    print(f"✅ Успешно установлено: {success_count}")
    if fail_count > 0:
        print(f"❌ Ошибок при установке: {fail_count}")
    
    return 0 if fail_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

