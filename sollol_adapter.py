"""
SOLLOL Adapter for SynapticLlamas

SOLLOL is a DROP-IN REPLACEMENT for Ollama that provides intelligent routing,
load balancing, and failover.

Key Concept:
- SOLLOL runs on port 11434 (same as Ollama)
- Agents point to http://localhost:11434 as usual
- SOLLOL routes to actual Ollama nodes (11435, 11436, 11437...)
- ZERO configuration changes needed!

Architecture:
    Agent → SOLLOL (11434) → Ollama nodes (11435, 11436, 11437...)

Usage:
    # Start SOLLOL (replaces Ollama on 11434)
    sollol serve --host 0.0.0.0 --port 11434

    # Agents work exactly as before - NO CHANGES NEEDED
    agent = Researcher()  # Points to localhost:11434 (now SOLLOL)
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SOLLOLAdapter:
    """
    Configuration adapter for using SOLLOL with SynapticLlamas.

    SOLLOL is a drop-in replacement for Ollama - agents use the same URL,
    but get intelligent routing, failover, and monitoring automatically.
    """

    def __init__(
        self,
        ollama_host: str = "localhost",
        ollama_port: int = 11434,
        use_sollol: bool = True
    ):
        """
        Initialize SOLLOL adapter.

        Args:
            ollama_host: Ollama/SOLLOL server hostname
            ollama_port: Ollama/SOLLOL server port (default: 11434)
            use_sollol: Whether SOLLOL is running (vs native Ollama)
        """
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.use_sollol = use_sollol

        # Check environment variables (standard Ollama vars)
        self.ollama_host = os.getenv("OLLAMA_HOST", self.ollama_host)
        self.ollama_port = int(os.getenv("OLLAMA_PORT", self.ollama_port))

        # Optional: detect if SOLLOL is running
        self.use_sollol = os.getenv("USE_SOLLOL", "true").lower() == "true"

    def get_ollama_url(self) -> str:
        """
        Get the URL to use for Ollama/SOLLOL API calls.

        Returns the same URL whether SOLLOL or native Ollama is running.
        This is the beauty of drop-in replacement!

        Returns:
            URL string (e.g., http://localhost:11434)
        """
        url = f"http://{self.ollama_host}:{self.ollama_port}"

        if self.use_sollol:
            logger.info(f"🚀 Using SOLLOL at {url} (intelligent routing enabled)")
        else:
            logger.info(f"⚙️  Using native Ollama at {url} (standard mode)")

        return url

    def check_sollol_available(self) -> bool:
        """
        Check if SOLLOL server is running (vs native Ollama).

        SOLLOL identifies itself via a custom header or dashboard endpoint.

        Returns:
            True if SOLLOL is running, False if native Ollama
        """
        import requests

        try:
            url = f"http://{self.ollama_host}:{self.ollama_port}/health"
            response = requests.get(url, timeout=2)

            # SOLLOL adds a custom header to identify itself
            if response.headers.get("X-Powered-By") == "SOLLOL":
                logger.info("✅ SOLLOL detected - intelligent routing enabled")
                self.use_sollol = True
                return True

        except Exception:
            pass

        # Try dashboard endpoint (SOLLOL-specific)
        try:
            url = f"http://{self.ollama_host}:{self.ollama_port}/dashboard.html"
            response = requests.head(url, timeout=2)
            if response.status_code == 200:
                logger.info("✅ SOLLOL detected via dashboard endpoint")
                self.use_sollol = True
                return True
        except Exception:
            pass

        logger.info("⚙️  Native Ollama detected (no SOLLOL features)")
        self.use_sollol = False
        return False

    def get_priority_for_agent(self, agent_name: str) -> int:
        """
        Get priority level for a specific agent type.

        Different agents can have different priorities for SOLLOL routing:
        - Critical agents get higher priority (faster nodes)
        - Background agents get lower priority (use available capacity)

        Args:
            agent_name: Name of the agent

        Returns:
            Priority level (1-10, where 10 is highest)
        """
        priority_map = {
            "Researcher": 7,     # High priority - user-facing
            "Critic": 6,         # Medium-high - analysis
            "Editor": 5,         # Medium - final processing
            "Summarizer": 4,     # Medium-low - can wait
            "Background": 2,     # Low - batch processing
        }

        return priority_map.get(agent_name, 5)  # Default: medium priority


# Global adapter instance
_adapter: Optional[SOLLOLAdapter] = None


def get_adapter() -> SOLLOLAdapter:
    """Get global SOLLOL adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = SOLLOLAdapter()
    return _adapter


def configure_sollol(
    host: str = "localhost",
    port: int = 8000,
    enabled: bool = True
) -> SOLLOLAdapter:
    """
    Configure SOLLOL integration globally.

    Args:
        host: SOLLOL server hostname
        port: SOLLOL server port
        enabled: Whether to enable SOLLOL

    Returns:
        Configured adapter instance
    """
    global _adapter
    _adapter = SOLLOLAdapter(host, port, enabled)
    return _adapter
