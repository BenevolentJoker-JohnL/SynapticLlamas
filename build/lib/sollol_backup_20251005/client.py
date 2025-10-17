"""
SOLLOL Client SDK - Plug-and-play integration for AI applications.

Simple one-line integration:
    from sollol.client import SOLLOLClient
    sollol = SOLLOLClient()
    response = sollol.chat("Hello!")
"""
from typing import List, Dict, Optional, Any
import httpx
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SOLLOLConfig:
    """SOLLOL client configuration."""

    base_url: str = "http://localhost:8000"
    timeout: int = 300
    default_model: str = "llama3.2"
    default_priority: int = 5


class SOLLOLClient:
    """
    Plug-and-play SOLLOL client for AI applications.

    Zero-config usage:
        sollol = SOLLOLClient()
        response = sollol.chat("Hello, world!")

    With configuration:
        config = SOLLOLConfig(base_url="http://sollol-server:8000")
        sollol = SOLLOLClient(config)
    """

    def __init__(self, config: Optional[SOLLOLConfig] = None):
        """
        Initialize SOLLOL client.

        Args:
            config: Optional configuration (uses defaults if not provided)
        """
        self.config = config or SOLLOLConfig()
        self.client = httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout)
        self._async_client = None

    def chat(
        self,
        message: str,
        model: Optional[str] = None,
        priority: Optional[int] = None,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Send a chat message with intelligent routing.

        Args:
            message: User message
            model: Model to use (default: llama3.2)
            priority: Request priority 1-10 (default: 5)
            system_prompt: Optional system prompt
            conversation_history: Optional previous messages

        Returns:
            Response dict with message and routing metadata

        Example:
            >>> response = sollol.chat("Explain quantum computing")
            >>> print(response['message']['content'])
            >>> print(f"Routed to: {response['_sollol_routing']['host']}")
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": message})

        payload = {
            "model": model or self.config.default_model,
            "messages": messages
        }

        response = self.client.post(
            "/api/chat",
            params={"priority": priority or self.config.default_priority},
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def chat_async(
        self,
        message: str,
        model: Optional[str] = None,
        priority: Optional[int] = None,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Async version of chat()."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout
            )

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": message})

        payload = {
            "model": model or self.config.default_model,
            "messages": messages
        }

        response = await self._async_client.post(
            "/api/chat",
            params={"priority": priority or self.config.default_priority},
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def embed(
        self,
        text: str,
        model: str = "nomic-embed-text"
    ) -> List[float]:
        """
        Get embeddings for text.

        Args:
            text: Text to embed
            model: Embedding model to use

        Returns:
            Embedding vector

        Example:
            >>> vector = sollol.embed("This is a test document")
            >>> len(vector)
            768
        """
        response = self.client.post(
            "/api/embed",
            json={"text": text, "model": model}
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def batch_embed(
        self,
        documents: List[str],
        model: str = "nomic-embed-text"
    ) -> Dict:
        """
        Queue documents for batch embedding (via Dask).

        Args:
            documents: List of documents to embed
            model: Embedding model to use

        Returns:
            Queue status

        Example:
            >>> docs = ["Doc 1", "Doc 2", "Doc 3"]
            >>> status = sollol.batch_embed(docs)
            >>> print(status['count'])
            3
        """
        response = self.client.post(
            "/api/embed/batch",
            json={"docs": documents, "model": model}
        )
        response.raise_for_status()
        return response.json()

    def health(self) -> Dict:
        """
        Check SOLLOL health status.

        Returns:
            Health status including available hosts

        Example:
            >>> health = sollol.health()
            >>> print(f"Status: {health['status']}")
            >>> print(f"Hosts: {len(health['hosts'])}")
        """
        response = self.client.get("/api/health")
        response.raise_for_status()
        return response.json()

    def stats(self) -> Dict:
        """
        Get performance statistics and routing intelligence.

        Returns:
            Detailed stats including routing patterns

        Example:
            >>> stats = sollol.stats()
            >>> for host in stats['hosts']:
            ...     print(f"{host['host']}: {host['latency_ms']:.0f}ms")
        """
        response = self.client.get("/api/stats")
        response.raise_for_status()
        return response.json()

    def dashboard(self) -> Dict:
        """
        Get real-time dashboard data.

        Returns:
            Dashboard data with alerts and performance metrics
        """
        response = self.client.get("/api/dashboard")
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close HTTP client connections."""
        self.client.close()
        if self._async_client:
            import asyncio
            asyncio.run(self._async_client.aclose())

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close on context exit."""
        self.close()


# Convenience function for quick usage
def connect(base_url: str = "http://localhost:8000", **kwargs) -> SOLLOLClient:
    """
    Quick connection to SOLLOL.

    Args:
        base_url: SOLLOL gateway URL
        **kwargs: Additional SOLLOLConfig parameters

    Returns:
        Configured SOLLOLClient

    Example:
        >>> sollol = connect()
        >>> response = sollol.chat("Hello!")
    """
    config = SOLLOLConfig(base_url=base_url, **kwargs)
    return SOLLOLClient(config)


# ===================================================================
# Zero-Config Ollama Client (Direct node access, no SOLLOL gateway)
# ===================================================================

from .pool import OllamaPool


class Ollama:
    """
    Zero-config Ollama client with automatic load balancing and distributed inference.

    No configuration needed - just create and use. Automatically discovers
    Ollama nodes and load balances across them. Optionally supports llama.cpp
    distributed inference for large models (70B+).

    This is different from SOLLOLClient:
    - SOLLOLClient: Connects to SOLLOL gateway (http://localhost:8000)
    - Ollama: Connects directly to Ollama nodes (auto-discovered)

    Usage:
        from sollol import Ollama

        # Basic usage (Ollama only)
        client = Ollama()
        response = client.chat("llama3.2", "Hello!")

        # With distributed inference for large models
        client = Ollama(enable_distributed=True, rpc_nodes=[
            {"host": "192.168.1.10", "port": 50052},
            {"host": "192.168.1.11", "port": 50052}
        ])
        response = client.chat("llama3.1:405b", "Explain quantum computing")
    """

    def __init__(
        self,
        nodes: Optional[List[Dict[str, str]]] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        enable_distributed: bool = False,
        rpc_nodes: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Initialize Ollama client with optional distributed inference.

        AUTOMATIC GGUF RESOLUTION: Models are automatically extracted from Ollama's
        blob storage. No need to specify GGUF paths - just pull the model in Ollama!

        Args:
            nodes: List of Ollama node dicts (optional, auto-discovers if not provided)
            host: Single host (convenience, creates single-node pool)
            port: Port for single host (default: 11434)
            enable_distributed: Enable llama.cpp distributed inference for large models
            rpc_nodes: llama.cpp RPC backend nodes for distributed inference
                      Format: [{"host": "ip", "port": 50052}]
                      Note: No model_path needed - auto-resolved from Ollama!
        """
        # Handle single host convenience parameter
        if host is not None:
            port = port or 11434
            nodes = [{"host": host, "port": str(port)}]

        # Create pool (auto-discovers if nodes=None)
        self.pool = OllamaPool(nodes=nodes)

        # Setup hybrid routing if distributed enabled
        self.hybrid_router = None
        self.enable_distributed = enable_distributed

        if enable_distributed and rpc_nodes:
            from .hybrid_router import HybridRouter

            # Create hybrid router with automatic GGUF resolution from Ollama storage
            self.hybrid_router = HybridRouter(
                ollama_pool=self.pool,
                rpc_backends=rpc_nodes,  # Just pass the dicts directly
                enable_distributed=True
            )

            logger.info("🚀 Ollama client initialized with distributed inference support")
            logger.info("   Models will be auto-resolved from Ollama storage (no GGUF paths needed!)")

    def chat(
        self,
        model: str,
        messages: Any,  # Can be str or List[Dict]
        **kwargs
    ) -> str:
        """
        Chat completion with automatic routing.

        Automatically routes to:
        - Ollama pool for small/medium models (<= 70B)
        - llama.cpp distributed cluster for large models (> 70B)

        Args:
            model: Model name (e.g., "llama3.2", "llama3.1:405b")
            messages: Either a string (converted to user message) or list of message dicts
            **kwargs: Additional Ollama parameters

        Returns:
            Response text

        Example:
            >>> client = Ollama()
            >>> response = client.chat("llama3.2", "Hello!")
            >>> print(response)

            >>> # With distributed inference
            >>> client = Ollama(enable_distributed=True, rpc_nodes=[...])
            >>> response = client.chat("llama3.1:405b", "Explain quantum computing")
            >>> print(response)
        """
        # Convert string to messages format
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        # Route based on whether distributed is enabled and model size
        if self.hybrid_router:
            # Use hybrid router for intelligent backend selection
            import asyncio
            result = asyncio.run(
                self.hybrid_router.route_request(model, messages, **kwargs)
            )
        else:
            # Use standard Ollama pool
            result = self.pool.chat(model=model, messages=messages, **kwargs)

        # Extract text from response
        return result.get('message', {}).get('content', '')

    def generate(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Generate text.

        Args:
            model: Model name
            prompt: Text prompt
            **kwargs: Additional Ollama parameters

        Returns:
            Generated text

        Example:
            >>> client = Ollama()
            >>> text = client.generate("llama3.2", "Once upon a time")
            >>> print(text)
        """
        result = self.pool.generate(model=model, prompt=prompt, **kwargs)
        return result.get('response', '')

    def embed(
        self,
        model: str,
        text: str,
        **kwargs
    ) -> List[float]:
        """
        Generate embeddings.

        Args:
            model: Embedding model name (e.g., "mxbai-embed-large")
            text: Text to embed
            **kwargs: Additional Ollama parameters

        Returns:
            Embedding vector

        Example:
            >>> client = Ollama()
            >>> embedding = client.embed("mxbai-embed-large", "Hello world")
            >>> print(len(embedding))
            1024
        """
        result = self.pool.embed(model=model, input=text, **kwargs)

        # Handle different response formats
        embeddings = result.get('embeddings', [[]])[0] if result.get('embeddings') else result.get('embedding', [])
        return embeddings

    def get_stats(self) -> Dict[str, Any]:
        """Get load balancing statistics."""
        return self.pool.get_stats()

    def __repr__(self):
        stats = self.pool.get_stats()
        return f"Ollama(nodes={stats['nodes_configured']}, requests={stats['total_requests']})"
