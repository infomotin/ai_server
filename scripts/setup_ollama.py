#!/usr/bin/env python3
"""
Ollama setup helper script.
Checks Ollama installation and helps download initial models.
"""

import os
import sys
import subprocess
import requests
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.inference.ollama_client import ollama_client
from src.config import settings


def check_ollama_installed():
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Ollama is installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    print("✗ Ollama is not installed")
    print("\nTo install Ollama, run:")
    print("  curl -fsSL https://ollama.com/install.sh | sh")
    print("\nOr visit: https://ollama.com/download")
    return False


def check_ollama_service():
    url = settings.inference.ollama.base_url
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✓ Ollama service is running at {url}")
            return True
    except requests.exceptions.RequestException:
        pass

    print(f"✗ Ollama service is not running at {url}")
    print("\nStart Ollama with: ollama serve")
    return False


async def check_models():
    print("\nChecking installed models...")
    try:
        models = await ollama_client.list_models()
        if models:
            print(f"✓ {len(models)} models installed:")
            for m in models:
                print(f"  - {m.get('name', 'Unknown')}")
        else:
            print("✗ No models installed")
        return models
    except Exception as e:
        print(f"✗ Error checking models: {e}")
        return []


async def pull_model(model_id: str):
    print(f"\nPulling model: {model_id}")
    print("(This may take several minutes...)\n")

    try:
        async for status in ollama_client.pull_model(model_id):
            if "status" in status:
                print(f"  {status.get('status', '')}", end="\r")

        print(f"\n✓ Model {model_id} installed successfully!")
    except Exception as e:
        print(f"\n✗ Error pulling model: {e}")


def main():
    print("=" * 50)
    print("OpenLocalAI - Ollama Setup Helper")
    print("=" * 50)

    print("\n[1] Checking Ollama installation...")
    installed = check_ollama_installed()

    if installed:
        print("\n[2] Checking Ollama service...")
        running = check_ollama_service()

        if running:
            print("\n[3] Checking installed models...")
            asyncio.run(check_models())

            print("\n" + "=" * 50)
            print("Ollama is ready! You can now:")
            print("  1. Run: python scripts/init_db.py")
            print("  2. Run: python src/main.py")
            print("  3. Access the API at http://localhost:8000")
            print("=" * 50)
    else:
        print("\nPlease install Ollama first.")


if __name__ == "__main__":
    main()
