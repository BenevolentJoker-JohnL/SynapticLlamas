"""
Zero-config Ollama connection pool with intelligent load balancing.

Auto-discovers nodes, manages connections, routes requests intelligently.
Thread-safe and ready to use immediately.

Features full SynapticLlamas observability:
- Intelligent routing with task analysis
- Performance tracking and learning
- Detailed logging of routing decisions
"""

import threading
import logging
import requests
import time
from typing import List, Dict, Any, Optional
from .intelligence import IntelligentRouter, get_router

logger = logging.getLogger(__name__)


class OllamaPool:
    """
    Connection pool that automatically discovers and load balances across Ollama nodes.

    Usage:
        pool = OllamaPool.auto_configure()
        response = pool.chat("llama3.2", [{"role": "user", "content": "Hi"}])
    """

    def __init__(
        self,
        nodes: Optional[List[Dict[str, str]]] = None,
        enable_intelligent_routing: bool = True,
        exclude_localhost: bool = False
    ):
        """
        Initialize connection pool with full observability.

        Args:
            nodes: List of node dicts. If None, auto-discovers.
            enable_intelligent_routing: Use intelligent routing (default: True)
            exclude_localhost: Skip localhost during discovery (for SOLLOL gateway)
        """
        self.nodes = nodes or []
        self.exclude_localhost = exclude_localhost
        self._lock = threading.Lock()
        self._current_index = 0

        # Auto-discover if no nodes provided
        if not self.nodes:
            self._auto_discover()

        # Initialize intelligent routing
        self.enable_intelligent_routing = enable_intelligent_routing
        self.router = get_router() if enable_intelligent_routing else None

        # Enhanced stats tracking with performance metrics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'nodes_used': {},
            'node_performance': {}  # Track performance per node
        }

        # Initialize node metadata for intelligent routing
        self._init_node_metadata()

        logger.info(
            f"OllamaPool initialized with {len(self.nodes)} nodes "
            f"(intelligent_routing={'enabled' if enable_intelligent_routing else 'disabled'})"
        )

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

        if self.exclude_localhost:
            logger.debug("Auto-discovering Ollama nodes (excluding localhost)...")
        else:
            logger.debug("Auto-discovering Ollama nodes...")

        nodes = discover_ollama_nodes(timeout=0.5, exclude_localhost=self.exclude_localhost)

        with self._lock:
            self.nodes = nodes
            if self.exclude_localhost and len(nodes) == 0:
                logger.info("No remote Ollama nodes found (localhost excluded)")
            else:
                logger.info(f"Auto-discovered {len(nodes)} nodes: {nodes}")

    def _init_node_metadata(self):
        """Initialize metadata for each node for intelligent routing."""
        with self._lock:
            for node in self.nodes:
                node_key = f"{node['host']}:{node['port']}"
                if node_key not in self.stats['node_performance']:
                    self.stats['node_performance'][node_key] = {
                        'host': node_key,
                        'latency_ms': 0.0,
                        'success_rate': 1.0,
                        'total_requests': 0,
                        'failed_requests': 0,
                        'available': True,
                        'cpu_load': 0.5,  # Default assumption
                        'gpu_free_mem': 0,  # Unknown until checked
                        'priority': 999  # Default priority
                    }

    def _select_node(
        self,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 5
    ) -> tuple[Dict[str, str], Optional[Dict[str, Any]]]:
        """
        Select best node for request using intelligent routing.

        Args:
            payload: Request payload for task analysis
            priority: Request priority (1-10)

        Returns:
            (selected_node, routing_decision) tuple
        """
        with self._lock:
            if not self.nodes:
                raise RuntimeError("No Ollama nodes available")

            # If intelligent routing is disabled or no payload, use round-robin
            if not self.enable_intelligent_routing or not payload:
                node = self.nodes[self._current_index % len(self.nodes)]
                self._current_index += 1
                return node, None

            # Use intelligent routing
            try:
                # Analyze request
                context = self.router.analyze_request(payload, priority=priority)

                # Get available hosts metadata
                available_hosts = list(self.stats['node_performance'].values())

                # Select optimal node
                selected_host, decision = self.router.select_optimal_node(
                    context, available_hosts
                )

                # Find matching node dict
                for node in self.nodes:
                    node_key = f"{node['host']}:{node['port']}"
                    if node_key == selected_host:
                        # Log the routing decision
                        logger.info(
                            f"🎯 Intelligent routing: {decision['reasoning']}"
                        )
                        return node, decision

                # Fallback if not found
                logger.warning(f"Selected host {selected_host} not in nodes, using fallback")
                node = self.nodes[self._current_index % len(self.nodes)]
                self._current_index += 1
                return node, None

            except Exception as e:
                logger.warning(f"Intelligent routing failed: {e}, falling back to round-robin")
                node = self.nodes[self._current_index % len(self.nodes)]
                self._current_index += 1
                return node, None

    def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        priority: int = 5,
        timeout: float = 30.0
    ) -> Any:
        """
        Make HTTP request to selected node with intelligent routing and performance tracking.

        Args:
            endpoint: API endpoint (e.g., '/api/chat')
            data: Request payload
            priority: Request priority (1-10)
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
        routing_decision = None

        for attempt in range(len(self.nodes)):
            # Select node with intelligent routing
            node, decision = self._select_node(payload=data, priority=priority)
            if decision:
                routing_decision = decision

            node_key = f"{node['host']}:{node['port']}"
            url = f"http://{node['host']}:{node['port']}{endpoint}"

            # Track request start time
            start_time = time.time()

            try:
                logger.debug(f"Request to {url}")

                response = requests.post(
                    url,
                    json=data,
                    timeout=timeout
                )

                # Calculate latency
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    # Success! Update metrics
                    with self._lock:
                        self.stats['successful_requests'] += 1
                        self.stats['nodes_used'][node_key] = \
                            self.stats['nodes_used'].get(node_key, 0) + 1

                        # Update node performance metrics
                        perf = self.stats['node_performance'][node_key]
                        perf['total_requests'] += 1

                        # Update running average latency
                        if perf['total_requests'] == 1:
                            perf['latency_ms'] = latency_ms
                        else:
                            perf['latency_ms'] = (
                                (perf['latency_ms'] * (perf['total_requests'] - 1) + latency_ms) /
                                perf['total_requests']
                            )

                        # Update success rate
                        perf['success_rate'] = (
                            (perf['total_requests'] - perf['failed_requests']) /
                            perf['total_requests']
                        )

                    # Log performance
                    logger.info(
                        f"✅ Request succeeded: {node_key} "
                        f"(latency: {latency_ms:.1f}ms, "
                        f"avg: {self.stats['node_performance'][node_key]['latency_ms']:.1f}ms)"
                    )

                    # Record performance for router learning
                    if self.router and 'model' in data:
                        task_type = routing_decision.get('task_type', 'generation') if routing_decision else 'generation'
                        self.router.record_performance(
                            task_type=task_type,
                            model=data['model'],
                            actual_duration_ms=latency_ms
                        )

                    return response.json()
                else:
                    errors.append(f"{url}: HTTP {response.status_code}")
                    self._record_failure(node_key, latency_ms)

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                errors.append(f"{url}: {str(e)}")
                logger.debug(f"Request failed: {e}")
                self._record_failure(node_key, latency_ms)

        # All nodes failed
        with self._lock:
            self.stats['failed_requests'] += 1

        raise RuntimeError(
            f"All Ollama nodes failed. Errors: {'; '.join(errors)}"
        )

    def _record_failure(self, node_key: str, latency_ms: float):
        """Record a failed request for a node."""
        with self._lock:
            if node_key in self.stats['node_performance']:
                perf = self.stats['node_performance'][node_key]
                perf['failed_requests'] += 1
                perf['total_requests'] += 1

                # Update success rate
                if perf['total_requests'] > 0:
                    perf['success_rate'] = (
                        (perf['total_requests'] - perf['failed_requests']) /
                        perf['total_requests']
                    )

                logger.warning(
                    f"❌ Request failed: {node_key} "
                    f"(success_rate: {perf['success_rate']:.1%})"
                )

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        priority: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Chat completion with intelligent routing and observability.

        Args:
            model: Model name (e.g., "llama3.2")
            messages: Chat messages
            stream: Stream response (not supported yet)
            priority: Request priority 1-10 (default: 5)
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

        return self._make_request('/api/chat', data, priority=priority)

    def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        priority: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text with intelligent routing and observability.

        Args:
            model: Model name
            prompt: Text prompt
            stream: Stream response (not supported yet)
            priority: Request priority 1-10 (default: 5)
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

        return self._make_request('/api/generate', data, priority=priority)

    def embed(
        self,
        model: str,
        input: str,
        priority: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate embeddings with intelligent routing and observability.

        Args:
            model: Embedding model name
            input: Text to embed
            priority: Request priority 1-10 (default: 5)
            **kwargs: Additional Ollama parameters

        Returns:
            Embedding response dict
        """
        data = {
            'model': model,
            'input': input,
            **kwargs
        }

        return self._make_request('/api/embed', data, priority=priority)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive pool statistics with performance metrics."""
        with self._lock:
            return {
                **self.stats,
                'nodes_configured': len(self.nodes),
                'nodes': [f"{n['host']}:{n['port']}" for n in self.nodes],
                'intelligent_routing_enabled': self.enable_intelligent_routing
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
