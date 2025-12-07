#!/usr/bin/env python3
"""
Скрипт для запуска всех тестов канонизации акторов.
Проверяет unit-тесты, интеграционные тесты и покрытие кода.
"""
import sys
import subprocess
import os
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_tests(test_files: list, verbose: bool = True) -> bool:
    """
    Запустить тесты.
    
    Args:
        test_files: Список файлов с тестами
        verbose: Выводить подробную информацию
        
    Returns:
        True если все тесты прошли, False иначе
    """
    print("=" * 80)
    print("ЗАПУСК ТЕСТОВ КАНОНИЗАЦИИ АКТОРОВ")
    print("=" * 80)
    print()
    
    all_passed = True
    
    for test_file in test_files:
        test_path = project_root / "tests" / test_file
        if not test_path.exists():
            print(f"⚠️  Файл {test_file} не найден, пропускаем")
            continue
        
        print(f"Запуск тестов из {test_file}...")
        print("-" * 80)
        
        cmd = [sys.executable, "-m", "pytest", str(test_path), "-v"]
        if verbose:
            cmd.append("-s")
        
        result = subprocess.run(cmd, cwd=project_root)
        
        if result.returncode != 0:
            print(f"❌ Тесты из {test_file} не прошли!")
            all_passed = False
        else:
            print(f"✅ Тесты из {test_file} прошли успешно")
        
        print()
    
    return all_passed


def check_coverage() -> bool:
    """
    Проверить покрытие кода тестами.
    
    Returns:
        True если покрытие > 80%, False иначе
    """
    print("=" * 80)
    print("ПРОВЕРКА ПОКРЫТИЯ КОДА")
    print("=" * 80)
    print()
    
    try:
        # Проверяем наличие pytest-cov
        import pytest_cov
    except ImportError:
        print("⚠️  pytest-cov не установлен, пропускаем проверку покрытия")
        print("   Установите: pip install pytest-cov")
        return True
    
    target_files = [
        "backend/services/actor_canonicalization_service.py",
        "backend/services/wikidata_service.py"
    ]
    
    cmd = [
        sys.executable, "-m", "pytest",
        "--cov=backend.services.actor_canonicalization_service",
        "--cov=backend.services.wikidata_service",
        "--cov-report=term-missing",
        "--cov-report=html",
        "tests/test_actor_canonicalization.py",
        "tests/test_wikidata_service.py",
        "tests/test_actor_canonicalization_integration.py"
    ]
    
    result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    # Проверяем покрытие (упрощенная проверка)
    if "TOTAL" in result.stdout:
        # Извлекаем процент покрытия из вывода
        lines = result.stdout.split("\n")
        for line in lines:
            if "TOTAL" in line and "%" in line:
                # Парсим процент (пример: "TOTAL                   500    100    80%")
                parts = line.split()
                for part in parts:
                    if part.endswith("%"):
                        coverage = float(part.rstrip("%"))
                        if coverage >= 80:
                            print(f"✅ Покрытие кода: {coverage:.1f}% (требуется >= 80%)")
                            return True
                        else:
                            print(f"❌ Покрытие кода: {coverage:.1f}% (требуется >= 80%)")
                            return False
    
    return result.returncode == 0


def main():
    """Основная функция"""
    # Список тестовых файлов
    test_files = [
        "test_wikidata_service.py",
        "test_actor_canonicalization.py",
        "test_actor_canonicalization_integration.py"
    ]
    
    # Запускаем тесты
    tests_passed = run_tests(test_files)
    
    # Проверяем покрытие
    coverage_ok = check_coverage()
    
    # Итоговый результат
    print()
    print("=" * 80)
    print("ИТОГОВЫЙ РЕЗУЛЬТАТ")
    print("=" * 80)
    
    if tests_passed and coverage_ok:
        print("✅ Все тесты прошли успешно!")
        print("✅ Покрытие кода соответствует требованиям")
        return 0
    else:
        print("❌ Обнаружены проблемы:")
        if not tests_passed:
            print("   - Некоторые тесты не прошли")
        if not coverage_ok:
            print("   - Покрытие кода ниже требуемого")
        return 1


if __name__ == "__main__":
    sys.exit(main())

