import socket
import threading
import logging
import json
from typing import List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from ollama_node import OllamaNode

logger = logging.getLogger(__name__)


class NodeRegistry:
    """Manages Ollama nodes: discovery, registration, health monitoring."""

    def __init__(self):
        self.nodes: Dict[str, OllamaNode] = {}
        self._lock = threading.Lock()

    def add_node(self, url: str, name: Optional[str] = None, priority: int = 0,
                 auto_probe: bool = True) -> OllamaNode:
        """
        Add a node manually.

        Args:
            url: Ollama API URL
            name: Optional friendly name
            priority: Priority level
            auto_probe: Automatically probe capabilities

        Returns:
            OllamaNode instance
        """
        with self._lock:
            # Check if already exists
            if url in self.nodes:
                logger.info(f"Node {url} already registered")
                return self.nodes[url]

            node = OllamaNode(url, name, priority)

            # Health check
            if node.health_check():
                if auto_probe:
                    node.probe_capabilities()

                self.nodes[url] = node
                logger.info(f"✅ Added node: {node.name} ({url})")
                return node
            else:
                logger.warning(f"❌ Node {url} failed health check, not added")
                raise ConnectionError(f"Node {url} is not reachable")

    def remove_node(self, url: str) -> bool:
        """
        Remove a node by URL.

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if url in self.nodes:
                node = self.nodes.pop(url)
                logger.info(f"Removed node: {node.name}")
                return True
            return False

    def discover_nodes(self, ip_range: str = "192.168.1.0/24", port: int = 11434,
                       timeout: float = 1.0, max_workers: int = 50) -> List[OllamaNode]:
        """
        Discover Ollama nodes on the network.

        Args:
            ip_range: CIDR notation (e.g., "192.168.1.0/24")
            port: Ollama port (default 11434)
            timeout: Connection timeout per IP
            max_workers: Parallel scan workers

        Returns:
            List of discovered nodes
        """
        logger.info(f"🔍 Discovering Ollama nodes on {ip_range}:{port}")

        # Parse CIDR
        ips = self._parse_cidr(ip_range)
        discovered = []

        # Parallel scan
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._probe_ip, ip, port, timeout): ip
                for ip in ips
            }

            for future in as_completed(futures):
                result = future.result()
                if result:
                    discovered.append(result)

        logger.info(f"✅ Discovered {len(discovered)} nodes")
        return discovered

    def _probe_ip(self, ip: str, port: int, timeout: float) -> Optional[OllamaNode]:
        """Probe a single IP for Ollama service."""
        url = f"http://{ip}:{port}"

        try:
            # Quick TCP port check first
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()

            if result == 0:
                # Port is open, try Ollama API
                node = OllamaNode(url, name=f"ollama-{ip}")
                if node.health_check(timeout=timeout):
                    node.probe_capabilities(timeout=timeout)

                    # Auto-add to registry
                    with self._lock:
                        if url not in self.nodes:
                            self.nodes[url] = node
                            logger.info(f"🔍 Discovered: {node}")

                    return node
        except Exception:
            pass

        return None

    def _parse_cidr(self, cidr: str) -> List[str]:
        """
        Parse CIDR notation into list of IPs.

        Args:
            cidr: CIDR notation (e.g., "192.168.1.0/24")

        Returns:
            List of IP addresses
        """
        import ipaddress
        try:
            network = ipaddress.IPv4Network(cidr, strict=False)
            return [str(ip) for ip in network.hosts()]
        except Exception as e:
            logger.error(f"Invalid CIDR: {cidr} - {e}")
            return []

    def health_check_all(self, timeout: float = 3.0) -> Dict[str, bool]:
        """
        Health check all registered nodes.

        Returns:
            Dict of {url: is_healthy}
        """
        results = {}

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(node.health_check, timeout): url
                for url, node in self.nodes.items()
            }

            for future in as_completed(futures):
                url = futures[future]
                results[url] = future.result()

        # Log unhealthy nodes
        unhealthy = [url for url, healthy in results.items() if not healthy]
        if unhealthy:
            logger.warning(f"⚠️  Unhealthy nodes: {unhealthy}")

        return results

    def get_healthy_nodes(self) -> List[OllamaNode]:
        """Get all healthy nodes."""
        return [node for node in self.nodes.values() if node.metrics.is_healthy]

    def get_gpu_nodes(self) -> List[OllamaNode]:
        """Get all nodes with GPU capabilities."""
        return [node for node in self.nodes.values()
                if node.metrics.is_healthy and node.capabilities.has_gpu]

    def get_node_by_url(self, url: str) -> Optional[OllamaNode]:
        """Get node by URL."""
        return self.nodes.get(url)

    def list_nodes(self) -> List[Dict]:
        """List all nodes as dictionaries."""
        return [node.to_dict() for node in self.nodes.values()]

    def save_config(self, filepath: str):
        """Save node configuration to JSON file."""
        config = {
            "nodes": [
                {
                    "url": node.url,
                    "name": node.name,
                    "priority": node.priority
                }
                for node in self.nodes.values()
            ]
        }

        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"💾 Saved {len(self.nodes)} nodes to {filepath}")

    def load_config(self, filepath: str):
        """Load node configuration from JSON file."""
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)

            for node_config in config.get('nodes', []):
                try:
                    self.add_node(
                        url=node_config['url'],
                        name=node_config.get('name'),
                        priority=node_config.get('priority', 0)
                    )
                except Exception as e:
                    logger.warning(f"Failed to load node {node_config['url']}: {e}")

            logger.info(f"📂 Loaded configuration from {filepath}")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")

    def __len__(self):
        return len(self.nodes)

    def __repr__(self):
        healthy = len(self.get_healthy_nodes())
        gpu = len(self.get_gpu_nodes())
        return f"NodeRegistry({len(self.nodes)} nodes, {healthy} healthy, {gpu} GPU)"
