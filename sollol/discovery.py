"""
Fast Ollama node discovery - returns in <1 second.

Tries multiple strategies in order:
1. Environment variable (instant)
2. Known locations (instant)
3. Network scan (parallel, ~500ms)
"""

import socket
import os
import logging
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def discover_ollama_nodes(timeout: float = 0.5, exclude_localhost: bool = False) -> List[Dict[str, str]]:
    """
    Discover Ollama nodes using multiple strategies.
    Returns in under 1 second.

    Args:
        timeout: Connection timeout per node
        exclude_localhost: If True, skip localhost (useful when SOLLOL runs on 11434)

    Returns:
        List of node dicts: [{"host": "192.168.1.10", "port": "11434"}, ...]
    """
    strategies = [
        lambda t: _from_environment(t, exclude_localhost),
        lambda t: _from_known_locations(t, exclude_localhost),
        lambda t: _from_network_scan(t, exclude_localhost),
    ]

    for strategy in strategies:
        nodes = strategy(timeout)
        if nodes:
            logger.debug(f"Discovered {len(nodes)} nodes via {strategy.__name__}")
            return nodes

    # Fallback: only use localhost if not excluded
    if not exclude_localhost:
        logger.debug("No nodes discovered, falling back to localhost")
        return [{"host": "localhost", "port": "11434"}]
    else:
        logger.debug("No remote Ollama nodes discovered (localhost excluded)")
        return []


def _from_environment(timeout: float, exclude_localhost: bool = False) -> List[Dict[str, str]]:
    """Check OLLAMA_HOST environment variable."""
    host = os.getenv('OLLAMA_HOST', '').strip()
    if host:
        parsed = _parse_host(host)
        # Skip if localhost and excluded
        if exclude_localhost and parsed['host'] in ('localhost', '127.0.0.1'):
            return []
        if _is_ollama_running(parsed['host'], int(parsed['port']), timeout):
            return [parsed]
    return []


def _from_known_locations(timeout: float, exclude_localhost: bool = False) -> List[Dict[str, str]]:
    """Check common Ollama locations."""
    locations = [
        ("localhost", 11434),
        ("127.0.0.1", 11434),
    ]

    # Skip localhost checks if excluded
    if exclude_localhost:
        return []

    results = []
    for host, port in locations:
        if _is_ollama_running(host, port, timeout):
            results.append({"host": host, "port": str(port)})

    return results


def _from_network_scan(timeout: float, exclude_localhost: bool = False) -> List[Dict[str, str]]:
    """
    Fast parallel network scan of local subnet.

    Only scans if no nodes found yet (last resort).
    """
    try:
        subnet = _get_local_subnet()
    except:
        return []

    def check_host(ip: str) -> Optional[Dict[str, str]]:
        """Check if Ollama is running on this IP."""
        # Skip localhost IPs if excluded
        if exclude_localhost and ip in ('127.0.0.1', f"{subnet}.1"):
            return None
        if _is_port_open(ip, 11434, timeout / 254):
            if _is_ollama_running(ip, 11434, timeout):
                return {"host": ip, "port": "11434"}
        return None

    # Scan common IPs first (faster)
    priority_ips = [f"{subnet}.{i}" for i in [1, 2, 10, 100, 254]]

    # Check priority IPs first
    with ThreadPoolExecutor(max_workers=10) as executor:
        for result in executor.map(check_host, priority_ips):
            if result:
                return [result]  # Found one, that's enough

    # If still nothing, scan full subnet (slower)
    all_ips = [f"{subnet}.{i}" for i in range(1, 255) if f"{subnet}.{i}" not in priority_ips]

    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_host, ip): ip for ip in all_ips}

        for future in as_completed(futures):
            result = future.result()
            if result:
                # Cancel remaining futures
                for f in futures:
                    f.cancel()
                return [result]

    return []


def _is_port_open(host: str, port: int, timeout: float) -> bool:
    """Quick TCP port check."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def _is_ollama_running(host: str, port: int, timeout: float) -> bool:
    """Verify Ollama API is actually running."""
    import requests
    try:
        resp = requests.get(
            f"http://{host}:{port}/api/tags",
            timeout=timeout
        )
        return resp.status_code == 200
    except:
        return False


def _get_local_subnet() -> str:
    """
    Get local subnet (e.g., '192.168.1').

    Uses trick: connect to external IP to find our local IP.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually connect, just determines route
        s.connect(('10.255.255.255', 1))
        local_ip = s.getsockname()[0]
        return '.'.join(local_ip.split('.')[:-1])
    finally:
        s.close()


def _parse_host(host_string: str) -> Dict[str, str]:
    """
    Parse host string into dict.

    Examples:
        "localhost" -> {"host": "localhost", "port": "11434"}
        "192.168.1.100:11434" -> {"host": "192.168.1.100", "port": "11434"}
        "http://example.com:11434" -> {"host": "example.com", "port": "11434"}
    """
    # Remove http:// or https://
    host_string = host_string.replace('http://', '').replace('https://', '')

    # Split host:port
    if ':' in host_string:
        host, port = host_string.rsplit(':', 1)
        return {"host": host, "port": port}
    else:
        return {"host": host_string, "port": "11434"}
