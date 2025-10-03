"""
SOLLOL Configuration - Application-level configuration management.
"""
from typing import List, Optional, Literal
from dataclasses import dataclass, field

@dataclass
class SOLLOLConfig:
    """
    Configuration for SOLLOL instance.

    All settings can be configured programmatically from within your application.
    """

    # Ray configuration
    ray_workers: int = 2
    """Number of Ray actor workers for handling concurrent requests"""

    # Dask configuration
    dask_workers: int = 2
    """Number of Dask workers for batch processing"""

    dask_scheduler: Optional[str] = None
    """External Dask scheduler address (e.g., 'tcp://10.0.0.1:8786'). If None, uses local cluster."""

    # OLLOL hosts
    hosts: List[str] = field(default_factory=lambda: ["127.0.0.1:11434"])
    """List of OLLOL (Ollama) host addresses in format 'host:port'"""

    # Gateway configuration
    gateway_port: int = 8000
    """Port for FastAPI gateway"""

    gateway_host: str = "0.0.0.0"
    """Host for FastAPI gateway"""

    # Routing strategy
    routing_strategy: Literal["performance", "round_robin", "priority"] = "performance"
    """
    Routing strategy for selecting OLLOL hosts:
    - performance: Route based on latency, success rate, and system load (adaptive)
    - round_robin: Simple round-robin distribution
    - priority: Use hosts in priority order (based on order in hosts list)
    """

    # Autobatch configuration
    autobatch_enabled: bool = True
    """Enable autonomous batch processing for embeddings"""

    autobatch_interval: int = 60
    """Seconds between autobatch processing cycles"""

    autobatch_min_batch_size: int = 1
    """Minimum number of documents to trigger a batch"""

    autobatch_max_batch_size: int = 100
    """Maximum documents to process in a single batch"""

    # Metrics configuration
    metrics_enabled: bool = True
    """Enable Prometheus metrics collection"""

    metrics_port: int = 9090
    """Port for Prometheus metrics server"""

    # Adaptive metrics configuration
    adaptive_metrics_enabled: bool = True
    """Enable dynamic metrics feedback loop for adaptive routing"""

    adaptive_metrics_interval: int = 30
    """Seconds between adaptive metrics updates"""

    # Health check configuration
    health_check_enabled: bool = True
    """Enable periodic health checks for OLLOL hosts"""

    health_check_interval: int = 120
    """Seconds between health check cycles"""

    # Retry configuration
    max_retries: int = 3
    """Maximum number of retries for failed requests"""

    retry_backoff_multiplier: float = 0.5
    """Exponential backoff multiplier for retries"""

    # Timeouts
    chat_timeout: float = 300.0
    """Timeout in seconds for chat completion requests"""

    embedding_timeout: float = 60.0
    """Timeout in seconds for embedding requests"""

    health_check_timeout: float = 5.0
    """Timeout in seconds for health checks"""

    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.ray_workers < 1:
            raise ValueError("ray_workers must be at least 1")

        if self.dask_workers < 1:
            raise ValueError("dask_workers must be at least 1")

        if not self.hosts:
            raise ValueError("At least one OLLOL host must be configured")

        if self.gateway_port < 1 or self.gateway_port > 65535:
            raise ValueError("gateway_port must be between 1 and 65535")

        if self.metrics_port < 1 or self.metrics_port > 65535:
            raise ValueError("metrics_port must be between 1 and 65535")

        if self.autobatch_interval < 1:
            raise ValueError("autobatch_interval must be at least 1 second")

        if self.adaptive_metrics_interval < 1:
            raise ValueError("adaptive_metrics_interval must be at least 1 second")

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "ray_workers": self.ray_workers,
            "dask_workers": self.dask_workers,
            "dask_scheduler": self.dask_scheduler,
            "hosts": self.hosts,
            "gateway_port": self.gateway_port,
            "gateway_host": self.gateway_host,
            "routing_strategy": self.routing_strategy,
            "autobatch_enabled": self.autobatch_enabled,
            "autobatch_interval": self.autobatch_interval,
            "metrics_enabled": self.metrics_enabled,
            "metrics_port": self.metrics_port,
            "adaptive_metrics_enabled": self.adaptive_metrics_enabled,
            "adaptive_metrics_interval": self.adaptive_metrics_interval,
        }

    @classmethod
    def from_dict(cls, config_dict: dict) -> "SOLLOLConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)
