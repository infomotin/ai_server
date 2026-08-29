#!/usr/bin/env python3
"""
Model download script for OpenLocalAI.
Downloads and manages models from Ollama.
"""

import sys
import os
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.inference.ollama_client import ollama_client
from src.models.engine import init_engine, get_db_session
from src.services.model_service import model_service


async def list_remote_models():
    print("Fetching available models from Ollama...")
    try:
        models = await ollama_client.list_models()
        print(f"\nFound {len(models)} models:\n")
        for model in models:
            name = model.get("name", "Unknown")
            size = model.get("size", 0)
            size_gb = size / (1024**3) if size else 0
            print(f"  - {name} ({size_gb:.2f} GB)")
        return models
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []


async def download_model(model_id: str):
    print(f"Downloading model: {model_id}")
    print("This may take several minutes depending on your internet connection...\n")

    init_engine()
    with get_db_session() as db:
        try:
            async for status in ollama_client.pull_model_stream(model_id):
                if "status" in status:
                    print(f"  {status.get('status', '')}", end="\r")

            model_service.download_model(db, model_id)
            print(f"\n\nModel {model_id} downloaded successfully!")
        except Exception as e:
            print(f"\n\nError downloading model: {e}")


async def sync_models():
    print("Syncing local model catalog with Ollama...")
    init_engine()

    with get_db_session() as db:
        models = await model_service.sync_with_ollama(db)
        print(f"\nSynced {len(models)} models:")
        for model in models:
            status = "✓" if model.is_downloaded else "✗"
            print(f"  [{status}] {model.id} ({model.provider})")


async def main():
    parser = argparse.ArgumentParser(description="OpenLocalAI Model Management")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    list_parser = subparsers.add_parser("list", help="List available models from Ollama")
    subparsers.add_parser("sync", help="Sync models with local database")

    download_parser = subparsers.add_parser("download", help="Download a model")
    download_parser.add_argument("model", help="Model ID (e.g., llama3.2:1b)")

    args = parser.parse_args()

    if args.command == "list":
        await list_remote_models()
    elif args.command == "sync":
        await sync_models()
    elif args.command == "download":
        await download_model(args.model)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
