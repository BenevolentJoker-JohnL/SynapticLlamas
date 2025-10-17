#!/usr/bin/env python3
"""
Standalone RPC backend heartbeat monitor using RPCBackendRegistry.

Monitors RPC backends and publishes heartbeat to dashboard every 30 seconds.
Uses SOLLOL's RPCBackendRegistry for intelligent health monitoring.
"""
import sys
import time
sys.path.insert(0, '/home/joker/.local/lib/python3.10/site-packages')

from sollol.rpc_registry import RPCBackendRegistry
from sollol.rpc_discovery import auto_discover_rpc_backends

def main():
    print("=" * 70)
    print("RPC Backend Heartbeat Monitor (using RPCBackendRegistry)")
    print("=" * 70)
    print("Auto-discovering RPC backends on network...")

    # Create registry and auto-discover backends
    registry = RPCBackendRegistry()

    # Try to discover RPC backends
    discovered = auto_discover_rpc_backends()
    if discovered:
        for backend in discovered:
            registry.add_backend(backend['host'], backend['port'])
        print(f"✅ Discovered {len(discovered)} RPC backend(s):")
        for backend in discovered:
            print(f"   • {backend['host']}:{backend['port']}")
    else:
        # Fallback to known backends if discovery fails
        print("⚠️  Auto-discovery found no backends, adding known hosts...")
        registry.add_backend("localhost", 50052)
        registry.add_backend("10.9.66.154", 50052)
        registry.add_backend("10.9.66.48", 50052)
        print(f"   • localhost:50052")
        print(f"   • 10.9.66.154:50052")
        print(f"   • 10.9.66.48:50052")

    print("\nPublishing heartbeats every 30 seconds to dashboard...")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            # Run health checks on all backends
            # This also publishes heartbeat to dashboard via NetworkObserver
            results = registry.health_check_all(timeout=1.0)

            # Print status
            healthy_count = sum(1 for is_healthy in results.values() if is_healthy)
            for address, is_healthy in results.items():
                status = "healthy" if is_healthy else "unreachable"
                icon = "✓" if is_healthy else "✗"
                print(f"{icon} {address} - {status}")

            print(f"📡 Heartbeat published: {healthy_count}/{len(results)} backends active\n")

            # Wait 30 seconds
            time.sleep(30)

        except KeyboardInterrupt:
            print("\n\nStopping RPC heartbeat monitor...")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(30)

if __name__ == "__main__":
    main()
