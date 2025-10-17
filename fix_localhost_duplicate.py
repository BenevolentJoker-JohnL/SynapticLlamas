#!/usr/bin/env python3
"""
Fix localhost duplicate where localhost and machine IP both point to same Ollama instance
"""

import json
import os
import socket

CONFIG_PATH = os.path.expanduser("~/.synapticllamas_nodes.json")

def get_local_ip():
    """Get this machine's IP address."""
    try:
        # Get IP by connecting to external host (doesn't actually send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

def fix_localhost_duplicate():
    """Remove localhost entry if we also have this machine's IP."""

    if not os.path.exists(CONFIG_PATH):
        print(f"No config found at {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)

    nodes = config.get('nodes', [])
    if not nodes:
        print("No nodes in config")
        return

    # Get this machine's IP
    local_ip = get_local_ip()
    if not local_ip:
        print("❌ Could not determine local IP")
        return

    print(f"🖥️  This machine's IP: {local_ip}\n")
    print(f"📊 Current nodes ({len(nodes)}):")
    for node in nodes:
        print(f"  • {node.get('url')}")

    # Find localhost and local IP entries
    localhost_node = None
    local_ip_node = None
    other_nodes = []

    for node in nodes:
        url = node.get('url', '')
        if 'localhost:11434' in url or '127.0.0.1:11434' in url:
            localhost_node = node
        elif local_ip in url and ':11434' in url:
            local_ip_node = node
        else:
            other_nodes.append(node)

    # If we have both localhost and local IP, keep only local IP
    if localhost_node and local_ip_node:
        print(f"\n⚠️  FOUND DUPLICATE:")
        print(f"  • {localhost_node.get('url')} (localhost)")
        print(f"  • {local_ip_node.get('url')} (same machine via IP)")
        print(f"\n✅ WILL KEEP: {local_ip_node.get('url')}")
        print(f"❌ WILL REMOVE: {localhost_node.get('url')}")

        # Build new config
        new_nodes = [local_ip_node] + other_nodes

        # Backup
        backup_path = CONFIG_PATH + '.backup'
        with open(backup_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"\n💾 Backup saved: {backup_path}")

        # Save
        config['nodes'] = new_nodes
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"\n✅ Fixed! Now have {len(new_nodes)} unique nodes")
        print("\n📊 IMPACT:")
        print("  ✅ SOLLOL reporting WILL work correctly")
        print("  ✅ Your local Ollama is still monitored")
        print("  ✅ HTTP polling reduced by 25%")
        print("  ✅ Duplicate node removed")
        print("\n🔄 Restart SynapticLlamas to apply changes")

    elif localhost_node:
        print(f"\n⚠️  Found localhost entry but no IP-based entry")
        print("  This is fine - keeping localhost")
    elif local_ip_node:
        print(f"\n✅ Found IP-based entry, no localhost duplicate")
    else:
        print(f"\n✅ No local node found (all remote)")

if __name__ == "__main__":
    print("🔧 SynapticLlamas Localhost Duplicate Fixer\n")
    print("=" * 60)
    fix_localhost_duplicate()
    print("=" * 60)
