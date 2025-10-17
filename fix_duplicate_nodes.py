#!/usr/bin/env python3
"""
Fix duplicate localhost node registrations in SynapticLlamas

This script removes duplicate localhost/127.0.0.1 entries from the node registry.
"""

import json
import os
import sys

CONFIG_PATH = os.path.expanduser("~/.synapticllamas_nodes.json")

def fix_duplicate_nodes():
    """Remove duplicate localhost entries."""

    if not os.path.exists(CONFIG_PATH):
        print(f"No node config found at {CONFIG_PATH}")
        return

    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)

        nodes = config.get('nodes', [])

        if not nodes:
            print("No nodes in config")
            return

        print(f"\n📊 Current nodes ({len(nodes)}):")
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
            print(f"\n⚠️  Found {len(localhost_nodes)} localhost duplicates:")
            for node in localhost_nodes:
                print(f"  • {node.get('url')}")

            # Keep only the first one (prefer localhost over 127.0.0.1)
            localhost_nodes_sorted = sorted(
                localhost_nodes,
                key=lambda n: (0 if 'localhost' in n.get('url', '') else 1)
            )

            kept_node = localhost_nodes_sorted[0]
            removed_nodes = localhost_nodes_sorted[1:]

            print(f"\n✅ Keeping: {kept_node.get('url')}")
            print(f"❌ Removing:")
            for node in removed_nodes:
                print(f"  • {node.get('url')}")

            # Build new node list
            new_nodes = [kept_node] + other_nodes

            # Save updated config
            config['nodes'] = new_nodes

            # Backup old config
            backup_path = CONFIG_PATH + '.backup'
            with open(backup_path, 'w') as f:
                json.dump({'nodes': nodes}, f, indent=2)
            print(f"\n💾 Backup saved to: {backup_path}")

            # Write new config
            with open(CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=2)

            print(f"✅ Fixed! Now have {len(new_nodes)} unique nodes")
            print("\nRestart SynapticLlamas for changes to take effect.")

        else:
            print("\n✅ No duplicates found")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔧 SynapticLlamas Node Duplicate Fixer\n")
    fix_duplicate_nodes()
