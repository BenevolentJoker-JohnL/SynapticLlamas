import socket
import threading
import logging
import json
from typing import List, Optional, Dict, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from ollama_node import OllamaNode
from node_cluster import NodeCluster, needs_partitioning

logger = logging.getLogger(__name__)


class NodeRegistry:
    """Manages Ollama nodes: discovery, registration, health monitoring."""

    def __init__(self):
        self.nodes: Dict[str, OllamaNode] = {}
        self.clusters: Dict[str, NodeCluster] = {}  # name -> cluster
        self._lock = threading.Lock()
        self._ip_cache: Dict[str, str] = {}  # Cache resolved IPs to avoid duplicate lookups

    def _resolve_host_ip(self, url: str) -> str:
        """
        Resolve hostname/URL to IP address for duplicate detection.

        Args:
            url: URL like http://localhost:11434 or http://10.9.66.154:11434

        Returns:
            IP address string
        """
        try:
            # Extract hostname from URL
            if '://' in url:
                hostname = url.split('://')[1].split(':')[0]
            else:
                hostname = url.split(':')[0]

            # Check cache first
            if hostname in self._ip_cache:
                return self._ip_cache[hostname]

            # Resolve to IP
            ip = socket.gethostbyname(hostname)
            self._ip_cache[hostname] = ip
            return ip
        except Exception as e:
            logger.debug(f"Could not resolve {url}: {e}")
            return url  # Return original if resolution fails

    def _is_duplicate_node(self, url: str) -> Optional[str]:
        """
        Check if this URL points to an already registered node.

        Args:
            url: URL to check

        Returns:
            URL of existing node if duplicate, None otherwise
        """
        new_ip = self._resolve_host_ip(url)

        for existing_url in self.nodes.keys():
            existing_ip = self._resolve_host_ip(existing_url)
            if new_ip == existing_ip:
                return existing_url

        return None

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
            # Check if already exists by URL
            if url in self.nodes:
                logger.info(f"Node {url} already registered")
                return self.nodes[url]

            # Check for duplicate by IP address
            duplicate_url = self._is_duplicate_node(url)
            if duplicate_url:
                logger.warning(
                    f"⚠️  Node {url} is a duplicate of {duplicate_url} (same IP). "
                    f"Using existing node instead."
                )
                return self.nodes[duplicate_url]

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

    def create_cluster(
        self,
        name: str,
        node_urls: List[str],
        model: str,
        partitioning_strategy: str = "even"
    ) -> NodeCluster:
        """
        Create a node cluster for distributed model inference.

        Args:
            name: Cluster identifier
            node_urls: List of node URLs to include in cluster
            model: Model to partition (e.g., "llama2:70b")
            partitioning_strategy: How to distribute layers

        Returns:
            NodeCluster instance

        Raises:
            ValueError: If nodes don't exist or insufficient
        """
        with self._lock:
            # Validate nodes exist and are healthy
            cluster_nodes = []
            for url in node_urls:
                node = self.nodes.get(url)
                if not node:
                    raise ValueError(f"Node {url} not found in registry")
                if not node.metrics.is_healthy:
                    raise ValueError(f"Node {url} is unhealthy, cannot add to cluster")
                cluster_nodes.append(node)

            if len(cluster_nodes) < 2:
                raise ValueError("Cluster requires at least 2 nodes")

            # Create cluster
            cluster = NodeCluster(
                name=name,
                nodes=cluster_nodes,
                model=model,
                partitioning_strategy=partitioning_strategy
            )

            self.clusters[name] = cluster
            logger.info(f"✅ Created cluster: {name} with {len(cluster_nodes)} nodes")
            return cluster

    def remove_cluster(self, name: str) -> bool:
        """Remove a cluster."""
        with self._lock:
            if name in self.clusters:
                cluster = self.clusters.pop(name)
                logger.info(f"🗑️  Removed cluster: {name}")
                return True
            return False

    def get_cluster(self, name: str) -> Optional[NodeCluster]:
        """Get cluster by name."""
        return self.clusters.get(name)

    def get_all_clusters(self) -> List[NodeCluster]:
        """Get all clusters."""
        return list(self.clusters.values())

    def get_healthy_clusters(self) -> List[NodeCluster]:
        """Get all healthy clusters."""
        # Note: health_check() is async in NodeCluster, so we check is_healthy property
        return [c for c in self.clusters.values() if c.is_healthy]

    def get_worker_for_model(
        self,
        model: str,
        prefer_cluster: bool = True
    ) -> Union[OllamaNode, NodeCluster, None]:
        """
        Get best worker (node or cluster) for a model.

        For large models (70B+), returns cluster if available.
        For small models, returns individual node.

        Args:
            model: Model name
            prefer_cluster: Prefer cluster for large models

        Returns:
            OllamaNode or NodeCluster, or None if unavailable
        """
        requires_partition = needs_partitioning(model)

        if requires_partition and prefer_cluster:
            # Look for cluster with this model
            for cluster in self.clusters.values():
                if cluster.model == model and cluster.is_healthy:
                    logger.info(f"🔗 Routing {model} to cluster: {cluster.name}")
                    return cluster

            # No cluster available - check if we can create one
            healthy_nodes = self.get_healthy_nodes()
            if len(healthy_nodes) >= 2:
                logger.info(
                    f"⚠️  No cluster for {model}, but {len(healthy_nodes)} nodes available. "
                    "Consider creating cluster with registry.create_cluster()"
                )

        # Fall back to individual node
        healthy_nodes = self.get_healthy_nodes()
        if healthy_nodes:
            # Use node with lowest load
            best_node = min(healthy_nodes, key=lambda n: n.calculate_load_score())
            logger.info(f"📍 Routing {model} to node: {best_node.name}")
            return best_node

        return None

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
        clusters = len(self.clusters)
        healthy_clusters = len(self.get_healthy_clusters())
        return (
            f"NodeRegistry({len(self.nodes)} nodes, {healthy} healthy, {gpu} GPU, "
            f"{clusters} clusters, {healthy_clusters} healthy clusters)"
        )
