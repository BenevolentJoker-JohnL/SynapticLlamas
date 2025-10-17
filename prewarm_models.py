#!/usr/bin/env python3
"""
Pre-warm models on all Ollama nodes to avoid first-request delays.

This script sends a simple prompt to each model on each node to ensure they're
loaded into memory before actual requests arrive.
"""
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ollama nodes
NODES = [
    "http://10.9.66.154:11434",
    "http://10.9.66.48:11434",
    "http://localhost:11434",
]

# Models to pre-warm (common models used by SynapticLlamas)
MODELS_TO_PREWARM = [
    "llama3.2:latest",
    "llama3.2:3b",
    "llama3.1:latest",
    "codellama:latest",
]

def prewarm_model(node_url: str, model: str) -> dict:
    """
    Pre-warm a model by sending a simple generation request.

    Args:
        node_url: Ollama node URL
        model: Model name

    Returns:
        Result dict with status
    """
    start_time = time.time()

    try:
        # Send a simple prompt to load the model
        url = f"{node_url}/api/generate"
        payload = {
            "model": model,
            "prompt": "Hello",
            "stream": False,
            "options": {
                "num_predict": 1  # Only generate 1 token to minimize time
            }
        }

        print(f"  ⏳ Pre-warming {model} on {node_url}...")

        response = requests.post(url, json=payload, timeout=120)

        elapsed = time.time() - start_time

        if response.status_code == 200:
            print(f"  ✓ {model} on {node_url}: READY ({elapsed:.1f}s)")
            return {
                "node": node_url,
                "model": model,
                "status": "success",
                "elapsed": elapsed
            }
        else:
            print(f"  ✗ {model} on {node_url}: HTTP {response.status_code}")
            return {
                "node": node_url,
                "model": model,
                "status": "error",
                "error": f"HTTP {response.status_code}",
                "elapsed": elapsed
            }

    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"  ✗ {model} on {node_url}: TIMEOUT ({elapsed:.1f}s)")
        return {
            "node": node_url,
            "model": model,
            "status": "timeout",
            "elapsed": elapsed
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ✗ {model} on {node_url}: {e}")
        return {
            "node": node_url,
            "model": model,
            "status": "error",
            "error": str(e),
            "elapsed": elapsed
        }

def check_model_exists(node_url: str, model: str) -> bool:
    """Check if a model exists on a node."""
    try:
        response = requests.get(f"{node_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return any(m.get("name") == model for m in models)
    except:
        pass
    return False

def main():
    print("=" * 70)
    print("Pre-warming Models on Ollama Nodes")
    print("=" * 70)

    # Collect tasks
    tasks = []
    for node_url in NODES:
        print(f"\n📡 Checking node: {node_url}")
        for model in MODELS_TO_PREWARM:
            if check_model_exists(node_url, model):
                tasks.append((node_url, model))
                print(f"  ✓ {model}: Found")
            else:
                print(f"  ⊘ {model}: Not found (skipping)")

    if not tasks:
        print("\n⚠️  No models to pre-warm!")
        return

    print(f"\n🔥 Pre-warming {len(tasks)} model instances...")
    print("=" * 70)

    results = []

    # Pre-warm models in parallel (max 3 concurrent to avoid overload)
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(prewarm_model, node, model): (node, model)
            for node, model in tasks
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("Pre-warming Summary")
    print("=" * 70)

    success = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] != "success"]

    print(f"\n✓ Success: {len(success)}/{len(results)}")
    print(f"✗ Failed: {len(errors)}/{len(results)}")

    if success:
        avg_time = sum(r["elapsed"] for r in success) / len(success)
        print(f"⏱  Average warmup time: {avg_time:.1f}s")

    if errors:
        print("\n⚠️  Failed to pre-warm:")
        for r in errors:
            print(f"  - {r['model']} on {r['node']}: {r.get('error', r['status'])}")

    print("\n" + "=" * 70)
    print("✓ Pre-warming complete! Models are loaded and ready.")
    print("=" * 70)

if __name__ == "__main__":
    main()
