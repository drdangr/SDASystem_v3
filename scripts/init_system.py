#!/usr/bin/env python3
"""
Initialize SDASystem with mock data (legacy helper).

NOTE:
Default startup no longer generates mock data. Prefer:
  python scripts/generate_mock_data.py --force
and then start the server.
"""
import sys
import os
import json
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.utils.mock_data_generator import MockDataGenerator


def generate_mock_data():
    """Generate mock data files"""
    print("=" * 60)
    print("Generating mock data...")
    print("=" * 60)

    # Create data directory
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)

    # Generate data
    generator = MockDataGenerator()
    generator.save_to_files(str(data_dir))
    
    # Load back from files to return
    data = {}
    for filename in ["news.json", "actors.json", "stories.json", "domains.json"]:
        with open(data_dir / filename, 'r', encoding='utf-8') as f:
            key = filename.split('.')[0]
            data[key] = json.load(f)

    print(f"✓ Generated {len(data['actors'])} actors")
    print(f"✓ Generated {len(data['news'])} news items")
    print(f"✓ Generated {len(data['stories'])} stories")
    print(f"✓ Saved to {data_dir}/")
    print()

    return data


def initialize_api(data, api_url="http://localhost:8000"):
    """Initialize API with mock data"""
    print("=" * 60)
    print("Initializing API with data...")
    print("=" * 60)

    try:
        # Check if API is running
        response = requests.get(f"{api_url}/api/health", timeout=2)
        if response.status_code != 200:
            print("⚠ API is not responding correctly")
            return False

        # Send initialization request
        print("Sending data to API...")
        response = requests.post(
            f"{api_url}/api/initialize",
            data=json.dumps(data, default=str),
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            print("✓ API initialized successfully")
            print(f"  - News: {result['stats']['news_count']}")
            print(f"  - Actors: {result['stats']['actors_count']}")
            print(f"  - Stories created: {result['stories_created']}")
            print(f"  - News edges: {result['stats']['news_edges']}")
            print()
            return True
        else:
            print(f"✗ API initialization failed: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("⚠ Could not connect to API. Is the server running?")
        print(f"  Start the server with: python main.py")
        return False
    except Exception as e:
        print(f"✗ Error initializing API: {e}")
        return False


def main():
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║       SDASystem v0.1 - Initialization Script             ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()

    # Generate mock data
    data = generate_mock_data()

    # Try to initialize API if it's running
    api_initialized = initialize_api(data)

    print("=" * 60)
    print("Next steps:")
    print("=" * 60)

    if not api_initialized:
        print("1. Start the API server:")
        print("   python main.py")
        print()
        print("2. Initialize the system:")
        print("   python scripts/init_system.py")
        print()
    else:
        print("✓ System is ready!")
        print()
        print("Open your browser and navigate to:")
        print("  → UI: http://localhost:8000/ui")
        print("  → API Docs: http://localhost:8000/docs")
        print()

    print("=" * 60)


if __name__ == "__main__":
    main()
