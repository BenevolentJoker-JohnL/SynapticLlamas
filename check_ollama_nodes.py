#!/usr/bin/env python3
"""
Check Ollama nodes and available models.
"""
import requests
import json

# Known Ollama nodes from logs
nodes = [
    "http://10.9.66.154:11434",
    "http://10.9.66.48:11434",
    "http://localhost:11434",
]

print("=" * 70)
print("Checking Ollama Nodes and Models")
print("=" * 70)

for node_url in nodes:
    print(f"\n📡 Node: {node_url}")
    print("-" * 70)

    # Check if node is reachable
    try:
        response = requests.get(f"{node_url}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])

            print(f"✓ Status: ONLINE")
            print(f"✓ Models available: {len(models)}")

            if models:
                print("\nModels:")
                for model in models:
                    name = model.get("name", "unknown")
                    size = model.get("size", 0)
                    size_gb = size / (1024**3)
                    modified = model.get("modified_at", "unknown")
                    print(f"  - {name:40s} {size_gb:6.2f} GB  {modified}")
            else:
                print("  ⚠️  No models found on this node!")
        else:
            print(f"✗ HTTP {response.status_code}: {response.text}")

    except requests.exceptions.Timeout:
        print(f"✗ Status: TIMEOUT (>5s)")
    except requests.exceptions.ConnectionError:
        print(f"✗ Status: CONNECTION REFUSED")
    except Exception as e:
        print(f"✗ Error: {e}")

print("\n" + "=" * 70)
print("\n💡 Recommendations:")
print("  1. Ensure llama3.2 model is pulled on all nodes")
print("  2. Use: curl http://NODE:11434/api/pull -d '{\"name\":\"llama3.2\"}'")
print("  3. Or use: ollama pull llama3.2 (on each node)")
print("=" * 70)
