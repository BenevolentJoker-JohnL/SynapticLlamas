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

    def health_check(self, timeout: float = 3.0) -> bool:
        """
        Check if node is healthy and responsive.

        Returns:
            True if healthy, False otherwise
        """
        try:
            start = time.time()
            response = requests.get(f"{self.url}/api/tags", timeout=timeout)
            elapsed = time.time() - start

            if response.status_code == 200:
                self.metrics.last_response_time = elapsed
                self.metrics.last_health_check = datetime.now()
                self.metrics.is_healthy = True

                # Update capabilities
                data = response.json()
                self.capabilities.models_loaded = [m['name'] for m in data.get('models', [])]

                return True
            else:
                self.metrics.is_healthy = False
                return False

        except Exception as e:
            logger.warning(f"Health check failed for {self.name}: {e}")
            self.metrics.is_healthy = False
            self.metrics.last_health_check = datetime.now()
            return False

    def probe_capabilities(self, timeout: float = 5.0) -> bool:
        """
        Probe node for GPU and hardware capabilities.

        Returns:
            True if probe successful
        """
        try:
            # Try to get model info to infer GPU presence
            response = requests.post(
                f"{self.url}/api/show",
                json={"name": "llama3.2"},  # Try a common model
                timeout=timeout
            )

            if response.status_code == 200:
                data = response.json()
                # Infer GPU from model details (this is heuristic)
                model_params = data.get('parameters', '')
                if 'gpu' in model_params.lower() or 'cuda' in model_params.lower():
                    self.capabilities.has_gpu = True

            # For now, set defaults (could be extended with system APIs)
            self.capabilities.cpu_cores = 4  # Default assumption
            self.capabilities.total_memory_mb = 8192  # Default assumption

            return True

        except Exception as e:
            logger.debug(f"Capability probe failed for {self.name}: {e}")
            return False

    def generate(self, model: str, prompt: str, system_prompt: Optional[str] = None,
                 format_json: bool = False, timeout: float = 120.0) -> Dict:
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
            response = requests.post(
                f"{self.url}/api/generate",
                json=payload,
                timeout=timeout
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

        except Exception as e:
            elapsed = time.time() - start
            self.metrics.failed_requests += 1
            self.metrics.total_requests += 1

            logger.error(f"Generation failed on {self.name}: {e}")
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
        # Keep only last 10 requests
        if len(self._last_request_times) > 10:
            self._last_request_times.pop(0)

        self.metrics.avg_response_time = sum(self._last_request_times) / len(self._last_request_times)

    def calculate_load_score(self) -> float:
        """
        Calculate load score (0-1, lower is better).
        Factors: response time, failure rate, current load.

        Returns:
            Load score between 0 and 1
        """
        if not self.metrics.is_healthy:
            return 1.0  # Maximum load = unhealthy

        # Failure rate component (0-0.5)
        failure_rate = 0.0
        if self.metrics.total_requests > 0:
            failure_rate = self.metrics.failed_requests / self.metrics.total_requests * 0.5

        # Response time component (0-0.5)
        # Normalize: assume 10s is max acceptable
        response_component = min(self.metrics.avg_response_time / 10.0, 1.0) * 0.5

        self.metrics.load_score = failure_rate + response_component
        return self.metrics.load_score

    def to_dict(self) -> Dict:
        """Convert node to dictionary representation."""
        return {
            "name": self.name,
            "url": self.url,
            "priority": self.priority,
            "is_healthy": self.metrics.is_healthy,
            "has_gpu": self.capabilities.has_gpu,
            "models_loaded": self.capabilities.models_loaded,
            "total_requests": self.metrics.total_requests,
            "failed_requests": self.metrics.failed_requests,
            "avg_response_time": round(self.metrics.avg_response_time, 3),
            "load_score": round(self.metrics.load_score, 3)
        }

    def __repr__(self):
        status = "✓" if self.metrics.is_healthy else "✗"
        gpu = "🎮" if self.capabilities.has_gpu else "💻"
        return f"{status} {gpu} {self.name} ({self.url}) - Load: {self.metrics.load_score:.2f}"
