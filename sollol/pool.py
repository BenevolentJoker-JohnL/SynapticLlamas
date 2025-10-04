"""
Zero-config Ollama connection pool with intelligent load balancing.

Auto-discovers nodes, manages connections, routes requests intelligently.
Thread-safe and ready to use immediately.
"""

import threading
import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class OllamaPool:
    """
    Connection pool that automatically discovers and load balances across Ollama nodes.

    Usage:
        pool = OllamaPool.auto_configure()
        response = pool.chat("llama3.2", [{"role": "user", "content": "Hi"}])
    """

    def __init__(self, nodes: Optional[List[Dict[str, str]]] = None):
        """
        Initialize connection pool.

        Args:
            nodes: List of node dicts. If None, auto-discovers.
        """
        self.nodes = nodes or []
        self._lock = threading.Lock()
        self._current_index = 0

        # Auto-discover if no nodes provided
        if not self.nodes:
            self._auto_discover()

        # Simple stats tracking
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'nodes_used': {}
        }

        logger.info(f"OllamaPool initialized with {len(self.nodes)} nodes")

    @classmethod
    def auto_configure(cls) -> 'OllamaPool':
        """
        Create pool with automatic discovery.

        Returns:
            OllamaPool instance ready to use
        """
        return cls(nodes=None)

    def _auto_discover(self):
        """Discover Ollama nodes automatically."""
        from .discovery import discover_ollama_nodes

        logger.debug("Auto-discovering Ollama nodes...")
        nodes = discover_ollama_nodes(timeout=0.5)

        with self._lock:
            self.nodes = nodes
            logger.info(f"Auto-discovered {len(nodes)} nodes: {nodes}")

    def _select_node(self) -> Dict[str, str]:
        """
        Select best node for request.

        Currently: Simple round-robin
        TODO: Integrate IntelligentRouter for smart selection
        """
        with self._lock:
            if not self.nodes:
                raise RuntimeError("No Ollama nodes available")

            # Round-robin selection
            node = self.nodes[self._current_index % len(self.nodes)]
            self._current_index += 1

            return node

    def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        timeout: float = 30.0
    ) -> Any:
        """
        Make HTTP request to selected node with fallback.

        Args:
            endpoint: API endpoint (e.g., '/api/chat')
            data: Request payload
            timeout: Request timeout

        Returns:
            Response data

        Raises:
            RuntimeError: If all nodes fail
        """
        # Track request
        with self._lock:
            self.stats['total_requests'] += 1

        # Try nodes until one succeeds
        errors = []

        for attempt in range(len(self.nodes)):
            node = self._select_node()
            url = f"http://{node['host']}:{node['port']}{endpoint}"

            try:
                logger.debug(f"Request to {url}")

                response = requests.post(
                    url,
                    json=data,
                    timeout=timeout
                )

                if response.status_code == 200:
                    # Success!
                    with self._lock:
                        self.stats['successful_requests'] += 1
                        node_key = f"{node['host']}:{node['port']}"
                        self.stats['nodes_used'][node_key] = \
                            self.stats['nodes_used'].get(node_key, 0) + 1

                    return response.json()
                else:
                    errors.append(f"{url}: HTTP {response.status_code}")

            except Exception as e:
                errors.append(f"{url}: {str(e)}")
                logger.debug(f"Request failed: {e}")

        # All nodes failed
        with self._lock:
            self.stats['failed_requests'] += 1

        raise RuntimeError(
            f"All Ollama nodes failed. Errors: {'; '.join(errors)}"
        )

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Chat completion with automatic load balancing.

        Args:
            model: Model name (e.g., "llama3.2")
            messages: Chat messages
            stream: Stream response (not supported yet)
            **kwargs: Additional Ollama parameters

        Returns:
            Chat response dict
        """
        if stream:
            raise NotImplementedError("Streaming not supported yet")

        data = {
            'model': model,
            'messages': messages,
            'stream': False,
            **kwargs
        }

        return self._make_request('/api/chat', data)

    def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text with automatic load balancing.

        Args:
            model: Model name
            prompt: Text prompt
            stream: Stream response (not supported yet)
            **kwargs: Additional Ollama parameters

        Returns:
            Generation response dict
        """
        if stream:
            raise NotImplementedError("Streaming not supported yet")

        data = {
            'model': model,
            'prompt': prompt,
            'stream': False,
            **kwargs
        }

        return self._make_request('/api/generate', data)

    def embed(
        self,
        model: str,
        input: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate embeddings with automatic load balancing.

        Args:
            model: Embedding model name
            input: Text to embed
            **kwargs: Additional Ollama parameters

        Returns:
            Embedding response dict
        """
        data = {
            'model': model,
            'input': input,
            **kwargs
        }

        return self._make_request('/api/embed', data)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                **self.stats,
                'nodes_configured': len(self.nodes),
                'nodes': [f"{n['host']}:{n['port']}" for n in self.nodes]
            }

    def add_node(self, host: str, port: int = 11434):
        """
        Add a node to the pool.

        Args:
            host: Node hostname/IP
            port: Node port
        """
        with self._lock:
            node = {"host": host, "port": str(port)}
            if node not in self.nodes:
                self.nodes.append(node)
                logger.info(f"Added node: {host}:{port}")

    def remove_node(self, host: str, port: int = 11434):
        """
        Remove a node from the pool.

        Args:
            host: Node hostname/IP
            port: Node port
        """
        with self._lock:
            node = {"host": host, "port": str(port)}
            if node in self.nodes:
                self.nodes.remove(node)
                logger.info(f"Removed node: {host}:{port}")

    def __repr__(self):
        return f"OllamaPool(nodes={len(self.nodes)}, requests={self.stats['total_requests']})"


# Global pool instance (lazy-initialized)
_global_pool: Optional[OllamaPool] = None
_pool_lock = threading.Lock()


def get_pool() -> OllamaPool:
    """
    Get or create the global Ollama connection pool.

    This is thread-safe and lazy-initializes the pool on first access.

    Returns:
        Global OllamaPool instance
    """
    global _global_pool

    if _global_pool is None:
        with _pool_lock:
            # Double-check locking
            if _global_pool is None:
                _global_pool = OllamaPool.auto_configure()

    return _global_pool
