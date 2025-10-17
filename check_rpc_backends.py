#!/usr/bin/env python3
"""
Check for active llama.cpp RPC backends.
"""
import socket
import time

# Common RPC ports for llama.cpp
RPC_PORTS = [50052, 50051, 50053, 50054, 50055]

# Nodes to check
NODES = [
    "localhost",
    "10.9.66.154",
    "10.9.66.48",
]

print("=" * 70)
print("Checking for llama.cpp RPC Backends")
print("=" * 70)

found_backends = []

for host in NODES:
    print(f"\n📡 Checking {host}...")
    for port in RPC_PORTS:
        try:
            # Try to connect to RPC port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                print(f"  ✓ RPC backend found on {host}:{port}")
                found_backends.append(f"{host}:{port}")
            else:
                print(f"  ⊘ Port {port}: closed")
        except Exception as e:
            print(f"  ✗ Port {port}: {e}")

print(f"\n{'=' * 70}")
print(f"Summary: Found {len(found_backends)} RPC backends")
if found_backends:
    for backend in found_backends:
        print(f"  - {backend}")
else:
    print("  ⚠️  No RPC backends found!")
    print("\n💡 To start llama.cpp RPC backend:")
    print("  llama-server --port 8080 --rpc 50052 --model /path/to/model.gguf")
print("=" * 70)
