"""
SOLLOL Client SDK - Plug-and-play integration for AI applications.

Simple one-line integration:
    from sollol.client import SOLLOLClient
    sollol = SOLLOLClient()
    response = sollol.chat("Hello!")
"""
from typing import List, Dict, Optional, Any
import httpx
from dataclasses import dataclass


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
