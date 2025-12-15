#!/usr/bin/env python3
"""
Generate mock data files for SDASystem.

WARNING: This script overwrites data files in the target directory.
Use --force to allow overwriting.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.mock_data_generator import MockDataGenerator


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate SDASystem mock data into a data/ directory.")
    p.add_argument(
        "--data-dir",
        default=str(PROJECT_ROOT / "data"),
        help="Target directory to write news.json/actors.json/stories.json/domains.json",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing data files without prompting",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    data_dir = Path(args.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    targets = [
        data_dir / "news.json",
        data_dir / "actors.json",
        data_dir / "stories.json",
        data_dir / "domains.json",
    ]

    existing = [p for p in targets if p.exists()]
    if existing and not args.force:
        print("Refusing to overwrite existing data files:")
        for p in existing:
            print(f"  - {p}")
        print("Re-run with --force to overwrite.")
        return 2

    print("=" * 60)
    print("Generating mock data...")
    print("=" * 60)
    generator = MockDataGenerator()
    generator.save_to_files(str(data_dir))
    print(f"✓ Saved to {data_dir}/")
    print("Files:")
    for p in targets:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


