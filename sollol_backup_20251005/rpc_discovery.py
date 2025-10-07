"""
RPC Backend Discovery - Auto-detect llama.cpp RPC servers on the network

Similar to Ollama discovery, this module scans the network for running
RPC servers (default port: 50052).
"""
import socket
import asyncio
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import httpx

logger = logging.getLogger(__name__)


def check_rpc_server(host: str, port: int = 50052, timeout: float = 1.0) -> bool:
    """
    Check if an RPC server is running at host:port.

    Args:
        host: IP address to check
        port: RPC port (default: 50052)
        timeout: Connection timeout in seconds

    Returns:
        True if RPC server is reachable
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def discover_rpc_backends(
    cidr: str = None,
    port: int = 50052,
    timeout: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Discover RPC backends on the network.

    Args:
        cidr: Network CIDR (e.g., "192.168.1.0/24"). Auto-detects if None.
        port: RPC port to scan (default: 50052)
        timeout: Connection timeout per host

    Returns:
        List of discovered backends: [{"host": "ip", "port": 50052}, ...]
    """
    backends = []

    # Skip localhost check - rely on network scan to find local machine
    # (prevents duplicate entries if local machine has a network IP)
    # logger.info(f"🔍 Checking localhost for RPC server on port {port}...")
    # if check_rpc_server('127.0.0.1', port, timeout):
    #     logger.info(f"   ✅ Found RPC server: 127.0.0.1:{port}")
    #     backends.append({"host": "127.0.0.1", "port": port})

    # Then check network
    if cidr is None:
        # Auto-detect local network
        cidr = _detect_local_network()
        if not cidr:
            logger.warning("Could not auto-detect network. Skipping network scan.")
            if backends:
                logger.info(f"✅ Discovered {len(backends)} RPC backends")
            return backends

    logger.info(f"🔍 Scanning {cidr} for RPC servers on port {port}...")

    # Parse CIDR to get IP range
    ips = _cidr_to_ips(cidr)

    # Scan in parallel
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {
            executor.submit(check_rpc_server, ip, port, timeout): ip
            for ip in ips
        }

        for future in futures:
            ip = futures[future]
            try:
                if future.result():
                    # Skip localhost if already added
                    if ip in ['127.0.0.1', 'localhost']:
                        continue
                    logger.info(f"   ✅ Found RPC server: {ip}:{port}")
                    backends.append({"host": ip, "port": port})
            except Exception as e:
                logger.debug(f"Error checking {ip}: {e}")

    logger.info(f"✅ Discovered {len(backends)} RPC backends")
    return backends


def _detect_local_network() -> str:
    """
    Auto-detect local network CIDR.

    Returns:
        CIDR string (e.g., "192.168.1.0/24") or None
    """
    try:
        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()

        # Assume /24 network
        network = ".".join(local_ip.split(".")[:-1]) + ".0/24"
        return network
    except Exception as e:
        logger.debug(f"Could not auto-detect network: {e}")
        return None


def _cidr_to_ips(cidr: str) -> List[str]:
    """
    Convert CIDR notation to list of IPs.

    Args:
        cidr: CIDR notation (e.g., "192.168.1.0/24")

    Returns:
        List of IP addresses in the range
    """
    import ipaddress
    return [str(ip) for ip in ipaddress.IPv4Network(cidr, strict=False)]


# Convenience function
def auto_discover_rpc_backends(port: int = 50052) -> List[Dict[str, Any]]:
    """
    Auto-discover RPC backends on the local network.

    Args:
        port: RPC port to scan (default: 50052)

    Returns:
        List of discovered backends
    """
    return discover_rpc_backends(port=port)


if __name__ == "__main__":
    # Test discovery
    logging.basicConfig(level=logging.INFO)

    print("Testing RPC backend discovery...")
    backends = auto_discover_rpc_backends()

    if backends:
        print(f"\n✅ Found {len(backends)} RPC backends:")
        for backend in backends:
            print(f"   → {backend['host']}:{backend['port']}")
    else:
        print("\n❌ No RPC backends found")
        print("   Make sure RPC servers are running:")
        print("   rpc-server --host 0.0.0.0 --port 50052 --mem 2048")
