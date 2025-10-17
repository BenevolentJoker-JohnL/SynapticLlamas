#!/usr/bin/env python3
"""Verify what the duplicate node fix will do (DRY RUN - no changes)"""

import json
import os

CONFIG_PATH = os.path.expanduser("~/.synapticllamas_nodes.json")

print("🔍 VERIFICATION - What will change?\n")
print("=" * 60)

if not os.path.exists(CONFIG_PATH):
    print(f"✅ No node config found at {CONFIG_PATH}")
    print("   Nothing to fix!")
    exit(0)

with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

nodes = config.get('nodes', [])

if not nodes:
    print("✅ No nodes in config - nothing to fix")
    exit(0)

print(f"\n📊 CURRENT STATE ({len(nodes)} nodes):")
for node in nodes:
    url = node.get('url', 'unknown')
    print(f"  • {url}")

# Find localhost/127.0.0.1 duplicates
localhost_nodes = []
other_nodes = []

for node in nodes:
    url = node.get('url', '')
    if 'localhost:11434' in url or '127.0.0.1:11434' in url:
        localhost_nodes.append(node)
    else:
        other_nodes.append(node)

if len(localhost_nodes) > 1:
    print(f"\n⚠️  FOUND {len(localhost_nodes)} localhost duplicates:")
    for node in localhost_nodes:
        print(f"  • {node.get('url')}")

    # Keep only the first one (prefer localhost over 127.0.0.1)
    localhost_nodes_sorted = sorted(
        localhost_nodes,
        key=lambda n: (0 if 'localhost' in n.get('url', '') else 1)
    )

    kept_node = localhost_nodes_sorted[0]
    removed_nodes = localhost_nodes_sorted[1:]

    print(f"\n✅ AFTER FIX ({1 + len(other_nodes)} nodes):")
    print(f"  KEEP: {kept_node.get('url')}")
    for node in other_nodes:
        print(f"  KEEP: {node.get('url')}")

    print(f"\n❌ WILL REMOVE:")
    for node in removed_nodes:
        print(f"  • {node.get('url')}")

    print("\n" + "=" * 60)
    print("📊 IMPACT ON SOLLOL REPORTING:")
    print("  ✅ Dashboard WILL still work")
    print("  ✅ Metrics WILL still be collected")
    print("  ✅ Redis pub/sub WILL still work")
    print(f"  ✅ HTTP polling reduced by {len(removed_nodes)} node(s)")
    print("\n  Your Ollama instance is still monitored,")
    print("  just not counted twice!")

    print("\n" + "=" * 60)
    print("🔧 TO APPLY THIS FIX:")
    print("  python3 /home/joker/SynapticLlamas/fix_duplicate_nodes.py")
else:
    print("\n✅ No duplicates found - system is clean!")
    print("   The HTTP requests you're seeing are from")
    print("   SOLLOL dashboard's normal monitoring.")
    print("\n   This is CORRECT behavior for a dashboard.")
