import requests
import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class NodeCapabilities:
    """Hardware capabilities of an Ollama node."""
    has_gpu: bool = False
    gpu_count: int = 0
    gpu_memory_mb: int = 0
    cpu_cores: int = 0
    total_memory_mb: int = 0
    models_loaded: list = field(default_factory=list)

    # SOLLOL compatibility property
    @property
    def cpu_count(self) -> int:
        """Alias for cpu_cores (SOLLOL compatibility)."""
        return self.cpu_cores


@dataclass
class NodeMetrics:
    """Performance metrics for an Ollama node."""
    total_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_response_time: float = 0.0
    last_health_check: Optional[datetime] = None
    is_healthy: bool = True
    load_score: float = 0.0  # 0-1, lower is better
    consecutive_failures: int = 0  # Track consecutive health check failures

    # SOLLOL compatibility properties
    @property
    def successful_requests(self) -> int:
        """SOLLOL compatibility: successful_requests instead of calculated value."""
        return self.total_requests - self.failed_requests

    @property
    def avg_latency(self) -> float:
        """SOLLOL compatibility: avg_latency (ms) instead of avg_response_time (s)."""
        return self.avg_response_time * 1000

    @property
    def last_error(self) -> Optional[str]:
        """SOLLOL compatibility: last_error tracking."""
        return None  # TODO: Add error tracking if needed


class OllamaNode:
    """Represents a single Ollama instance/node."""

    def __init__(self, url: str, name: Optional[str] = None, priority: int = 0):
        """
        Initialize an Ollama node.

        Args:
            url: Ollama API URL (e.g., http://192.168.1.100:11434)
            name: Optional friendly name
            priority: Priority level (higher = preferred)
        """
        self.url = url.rstrip('/')
        self.name = name or url
        self.priority = priority
        self.capabilities = NodeCapabilities()
        self.metrics = NodeMetrics()
        self._last_request_times = []  # Rolling window for avg calculation

    def health_check(self, timeout: float = 2.0, connection_timeout: float = 1.0) -> bool:
        """
        Check if node is healthy and responsive.

        Args:
            timeout: Total timeout (default 2s)
            connection_timeout: Connection timeout (default 1s)

        Returns:
            True if healthy, False otherwise
        """
        try:
            start = time.time()
            # Use separate connection and read timeouts for faster failure detection
            response = requests.get(
                f"{self.url}/api/tags",
                timeout=(connection_timeout, timeout)
            )
            elapsed = time.time() - start

            if response.status_code == 200:
                self.metrics.last_response_time = elapsed
                self.metrics.last_health_check = datetime.now()
                self.metrics.is_healthy = True
                self.metrics.consecutive_failures = 0  # Reset on success

                # Update capabilities
                data = response.json()
                self.capabilities.models_loaded = [m['name'] for m in data.get('models', [])]

                return True
            else:
                self.metrics.is_healthy = False
                self.metrics.consecutive_failures += 1
                return False

        except requests.exceptions.ConnectionError as e:
            # Fast-fail on connection errors (no route to host, etc.)
            logger.warning(f"Connection error for {self.name}: {e}")
            self.metrics.is_healthy = False
            self.metrics.last_health_check = datetime.now()
            self.metrics.consecutive_failures += 1
            return False
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout for {self.name}: {e}")
            self.metrics.is_healthy = False
            self.metrics.last_health_check = datetime.now()
            self.metrics.consecutive_failures += 1
            return False
        except Exception as e:
            logger.warning(f"Health check failed for {self.name}: {e}")
            self.metrics.is_healthy = False
            self.metrics.last_health_check = datetime.now()
            self.metrics.consecutive_failures += 1
            return False

    def probe_capabilities(self, timeout: float = 5.0) -> bool:
        """
        Probe node for GPU and hardware capabilities.

        Returns:
            True if probe successful
        """
        try:
            # Check /api/ps for GPU usage (size_vram > 0 means GPU is available)
            response = requests.get(
                f"{self.url}/api/ps",
                timeout=timeout
            )

            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])

                # Check if ANY loaded model is using VRAM (indicates GPU presence)
                total_vram_mb = 0
                for model in models:
                    vram_bytes = model.get('size_vram', 0)
                    if vram_bytes > 0:
                        self.capabilities.has_gpu = True
                        total_vram_mb += vram_bytes / (1024 * 1024)  # Convert to MB

                if self.capabilities.has_gpu:
                    self.capabilities.gpu_count = 1  # Assume single GPU for now
                    # Store total VRAM usage (not ideal but better than nothing)
                    # Ideally we'd get GPU memory capacity, but Ollama doesn't expose it
                    self.capabilities.gpu_memory_mb = int(total_vram_mb)
                    logger.debug(f"{self.name}: GPU detected ({self.capabilities.gpu_memory_mb}MB VRAM in use)")
                else:
                    logger.debug(f"{self.name}: No GPU detected (all models on CPU)")

            # Set defaults
            self.capabilities.cpu_cores = 4  # Default assumption
            self.capabilities.total_memory_mb = 8192  # Default assumption

            return True

        except Exception as e:
            logger.debug(f"Capability probe failed for {self.name}: {e}")
            return False

    def generate(self, model: str, prompt: str, system_prompt: Optional[str] = None,
                 format_json: bool = False, timeout: float = 30.0) -> Dict:
        """
        Generate a response from this node.

        Returns:
            Response dict with 'response' and 'metrics'
        """
        start = time.time()

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }

        if system_prompt:
            payload["system"] = system_prompt

        if format_json:
            payload["format"] = "json"

        try:
            # Use explicit connect and read timeouts
            connect_timeout = timeout / 2.0
            read_timeout = timeout / 2.0
            response = requests.post(
                f"{self.url}/api/generate",
                json=payload,
                timeout=(connect_timeout, read_timeout)
            )
            response.raise_for_status()
            elapsed = time.time() - start

            # Update metrics
            self.metrics.total_requests += 1
            self._update_avg_response_time(elapsed)
            self.metrics.last_response_time = elapsed

            result = response.json()
            return {
                "response": result.get("response", ""),
                "node": self.name,
                "elapsed": elapsed,
                "success": True
            }

        except requests.exceptions.Timeout as e:
            elapsed = time.time() - start
            self.metrics.failed_requests += 1
            self.metrics.total_requests += 1
            logger.error(f"Generation timed out on {self.name} after {elapsed:.2f}s: {e}")
            return {
                "response": "",
                "node": self.name,
                "elapsed": elapsed,
                "success": False,
                "error": f"Timeout after {elapsed:.2f}s: {str(e)}"
            }
        except requests.exceptions.ConnectionError as e:
            elapsed = time.time() - start
            self.metrics.failed_requests += 1
            self.metrics.total_requests += 1
            logger.error(f"Connection error on {self.name} after {elapsed:.2f}s: {e}")
            return {
                "response": "",
                "node": self.name,
                "elapsed": elapsed,
                "success": False,
                "error": f"Connection error after {elapsed:.2f}s: {str(e)}"
            }
        except requests.exceptions.HTTPError as e:
            elapsed = time.time() - start
            self.metrics.failed_requests += 1
            self.metrics.total_requests += 1
            logger.error(f"HTTP error on {self.name}: {e}")
            return {
                "response": "",
                "node": self.name,
                "elapsed": elapsed,
                "success": False,
                "error": f"HTTP error: {str(e)}"
            }
        except Exception as e:
            elapsed = time.time() - start
            self.metrics.failed_requests += 1
            self.metrics.total_requests += 1
            logger.error(f"Unexpected error on {self.name}: {e}")
            return {
                "response": "",
                "node": self.name,
                "elapsed": elapsed,
                "success": False,
                "error": str(e)
            }

    def _update_avg_response_time(self, elapsed: float):
        """Update rolling average response time."""
        self._last_request_times.append(elapsed)
        # Keep only last 100 requests
        if len(self._last_request_times) > 100:
            self._last_request_times.pop(0)

        self.metrics.avg_response_time = sum(self._last_request_times) / len(self._last_request_times)

    def calculate_load_score(self) -> float:
        """
        Calculate current load score (0-100).

        SOLLOL compatibility method. Higher score = higher load.

        Returns:
            Load score from 0-100
        """
        if self.metrics.total_requests == 0:
            return 0.0

        # Simple load calculation based on request count and response time
        # This is compatible with SOLLOL's expectations
        request_load = min(100.0, (self.metrics.total_requests / 100.0) * 100)
        latency_factor = min(1.0, self.metrics.avg_response_time / 10.0)  # Normalize to 10s

        return request_load * 0.7 + latency_factor * 30.0

    @property
    def is_healthy(self) -> bool:
        """Compatibility property for SOLLOL."""
        return self.metrics.is_healthy

    @property
    def last_health_check(self) -> Optional[datetime]:
        """Compatibility property for SOLLOL."""
        return self.metrics.last_health_check

    def to_dict(self) -> dict:
        """Convert node to dictionary for display."""
        return {
            'name': self.name,
            'url': self.url,
            'priority': self.priority,
            'healthy': self.metrics.is_healthy,
            'total_requests': self.metrics.total_requests,
            'success_rate': f"{(self.metrics.successful_requests / self.metrics.total_requests * 100) if self.metrics.total_requests > 0 else 100:.1f}%",
            'avg_latency_ms': f"{self.metrics.avg_latency:.0f}",
            'load_score': f"{self.calculate_load_score():.1f}",
            'has_gpu': self.capabilities.has_gpu if self.capabilities else False,
        }

    def __repr__(self):
        return f"OllamaNode(name={self.name}, url={self.url}, healthy={self.metrics.is_healthy})"
