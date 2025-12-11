import requests
import sys

try:
    response = requests.get("http://localhost:8000/api/system/init/status")
    response.raise_for_status()
    print(response.json())
except Exception as e:
    print(f"Error: {e}")


