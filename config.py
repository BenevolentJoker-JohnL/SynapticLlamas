"""Configuration management for SynapticLlamas."""
import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    """Network discovery and connection configuration."""
    default_port: int = 11434
    discovery_timeout: int = 2
    discovery_workers: int = 50
    health_check_interval: int = 30
    health_check_timeout: float = 2.0  # Fast timeout for health checks
    connection_timeout: float = 1.0  # Connection-specific timeout
    request_timeout: int = 120
    max_consecutive_failures: int = 3  # Remove node after N failures


@dataclass
class LoadBalancerConfig:
    """Load balancer configuration."""
    default_strategy: str = "least_loaded"
    enable_health_checks: bool = True
    enable_metrics: bool = True


@dataclass
class RetryConfig:
    """Retry and error handling configuration."""
    max_retries: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True
    backoff_multiplier: float = 2.0
    max_retry_delay: float = 30.0


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    enabled: bool = True
    failure_threshold: int = 5
    timeout: int = 60
    expected_exception: type = Exception


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    enabled: bool = False
    requests_per_minute: int = 60
    burst_size: int = 10


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    console: bool = True


@dataclass
class SecurityConfig:
    """Security configuration."""
    validate_inputs: bool = True
    max_input_length: int = 100000
    allowed_protocols: list = field(default_factory=lambda: ["http", "https"])
    require_https: bool = False


@dataclass
class MetricsConfig:
    """Metrics and monitoring configuration."""
    enabled: bool = True
    track_latency: bool = True
    track_throughput: bool = True
    track_errors: bool = True
    history_size: int = 1000


@dataclass
class SynapticLlamasConfig:
    """Main configuration for SynapticLlamas."""
    network: NetworkConfig = field(default_factory=NetworkConfig)
    load_balancer: LoadBalancerConfig = field(default_factory=LoadBalancerConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    @classmethod
    def from_file(cls, config_path: str) -> 'SynapticLlamasConfig':
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to configuration file

        Returns:
            SynapticLlamasConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(path, 'r') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading configuration: {e}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SynapticLlamasConfig':
        """
        Create configuration from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            SynapticLlamasConfig instance
        """
        config = cls()

        if 'network' in data:
            config.network = NetworkConfig(**data['network'])
        if 'load_balancer' in data:
            config.load_balancer = LoadBalancerConfig(**data['load_balancer'])
        if 'retry' in data:
            config.retry = RetryConfig(**data['retry'])
        if 'circuit_breaker' in data:
            config.circuit_breaker = CircuitBreakerConfig(**data['circuit_breaker'])
        if 'rate_limit' in data:
            config.rate_limit = RateLimitConfig(**data['rate_limit'])
        if 'logging' in data:
            config.logging = LoggingConfig(**data['logging'])
        if 'security' in data:
            config.security = SecurityConfig(**data['security'])
        if 'metrics' in data:
            config.metrics = MetricsConfig(**data['metrics'])

        return config

    @classmethod
    def from_env(cls) -> 'SynapticLlamasConfig':
        """
        Load configuration from environment variables.

        Environment variables should be prefixed with SYNAPTIC_
        For example: SYNAPTIC_NETWORK_DEFAULT_PORT=11434

        Returns:
            SynapticLlamasConfig instance
        """
        config = cls()

        # Network config
        if os.getenv('SYNAPTIC_NETWORK_DEFAULT_PORT'):
            config.network.default_port = int(os.getenv('SYNAPTIC_NETWORK_DEFAULT_PORT'))
        if os.getenv('SYNAPTIC_NETWORK_DISCOVERY_TIMEOUT'):
            config.network.discovery_timeout = int(os.getenv('SYNAPTIC_NETWORK_DISCOVERY_TIMEOUT'))
        if os.getenv('SYNAPTIC_NETWORK_DISCOVERY_WORKERS'):
            config.network.discovery_workers = int(os.getenv('SYNAPTIC_NETWORK_DISCOVERY_WORKERS'))
        if os.getenv('SYNAPTIC_NETWORK_HEALTH_CHECK_INTERVAL'):
            config.network.health_check_interval = int(os.getenv('SYNAPTIC_NETWORK_HEALTH_CHECK_INTERVAL'))
        if os.getenv('SYNAPTIC_NETWORK_REQUEST_TIMEOUT'):
            config.network.request_timeout = int(os.getenv('SYNAPTIC_NETWORK_REQUEST_TIMEOUT'))

        # Load balancer config
        if os.getenv('SYNAPTIC_LB_DEFAULT_STRATEGY'):
            config.load_balancer.default_strategy = os.getenv('SYNAPTIC_LB_DEFAULT_STRATEGY')
        if os.getenv('SYNAPTIC_LB_ENABLE_HEALTH_CHECKS'):
            config.load_balancer.enable_health_checks = os.getenv('SYNAPTIC_LB_ENABLE_HEALTH_CHECKS').lower() == 'true'

        # Retry config
        if os.getenv('SYNAPTIC_RETRY_MAX_RETRIES'):
            config.retry.max_retries = int(os.getenv('SYNAPTIC_RETRY_MAX_RETRIES'))
        if os.getenv('SYNAPTIC_RETRY_DELAY'):
            config.retry.retry_delay = float(os.getenv('SYNAPTIC_RETRY_DELAY'))
        if os.getenv('SYNAPTIC_RETRY_EXPONENTIAL_BACKOFF'):
            config.retry.exponential_backoff = os.getenv('SYNAPTIC_RETRY_EXPONENTIAL_BACKOFF').lower() == 'true'

        # Circuit breaker config
        if os.getenv('SYNAPTIC_CB_ENABLED'):
            config.circuit_breaker.enabled = os.getenv('SYNAPTIC_CB_ENABLED').lower() == 'true'
        if os.getenv('SYNAPTIC_CB_FAILURE_THRESHOLD'):
            config.circuit_breaker.failure_threshold = int(os.getenv('SYNAPTIC_CB_FAILURE_THRESHOLD'))
        if os.getenv('SYNAPTIC_CB_TIMEOUT'):
            config.circuit_breaker.timeout = int(os.getenv('SYNAPTIC_CB_TIMEOUT'))

        # Rate limit config
        if os.getenv('SYNAPTIC_RATE_LIMIT_ENABLED'):
            config.rate_limit.enabled = os.getenv('SYNAPTIC_RATE_LIMIT_ENABLED').lower() == 'true'
        if os.getenv('SYNAPTIC_RATE_LIMIT_RPM'):
            config.rate_limit.requests_per_minute = int(os.getenv('SYNAPTIC_RATE_LIMIT_RPM'))

        # Logging config
        if os.getenv('SYNAPTIC_LOG_LEVEL'):
            config.logging.level = os.getenv('SYNAPTIC_LOG_LEVEL')
        if os.getenv('SYNAPTIC_LOG_FILE'):
            config.logging.file = os.getenv('SYNAPTIC_LOG_FILE')
        if os.getenv('SYNAPTIC_LOG_CONSOLE'):
            config.logging.console = os.getenv('SYNAPTIC_LOG_CONSOLE').lower() == 'true'

        # Security config
        if os.getenv('SYNAPTIC_SECURITY_VALIDATE_INPUTS'):
            config.security.validate_inputs = os.getenv('SYNAPTIC_SECURITY_VALIDATE_INPUTS').lower() == 'true'
        if os.getenv('SYNAPTIC_SECURITY_MAX_INPUT_LENGTH'):
            config.security.max_input_length = int(os.getenv('SYNAPTIC_SECURITY_MAX_INPUT_LENGTH'))
        if os.getenv('SYNAPTIC_SECURITY_REQUIRE_HTTPS'):
            config.security.require_https = os.getenv('SYNAPTIC_SECURITY_REQUIRE_HTTPS').lower() == 'true'

        return config

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Configuration as dictionary
        """
        return {
            'network': asdict(self.network),
            'load_balancer': asdict(self.load_balancer),
            'retry': asdict(self.retry),
            'circuit_breaker': {k: v for k, v in asdict(self.circuit_breaker).items() if k != 'expected_exception'},
            'rate_limit': asdict(self.rate_limit),
            'logging': asdict(self.logging),
            'security': asdict(self.security),
            'metrics': asdict(self.metrics)
        }

    def save(self, config_path: str):
        """
        Save configuration to JSON file.

        Args:
            config_path: Path to save configuration file
        """
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"Configuration saved to {config_path}")

    def validate(self) -> bool:
        """
        Validate configuration values.

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        # Network validation
        if self.network.default_port < 1 or self.network.default_port > 65535:
            raise ValueError(f"Invalid port: {self.network.default_port}")
        if self.network.discovery_timeout < 1:
            raise ValueError(f"Discovery timeout must be >= 1: {self.network.discovery_timeout}")
        if self.network.discovery_workers < 1:
            raise ValueError(f"Discovery workers must be >= 1: {self.network.discovery_workers}")

        # Retry validation
        if self.retry.max_retries < 0:
            raise ValueError(f"Max retries must be >= 0: {self.retry.max_retries}")
        if self.retry.retry_delay < 0:
            raise ValueError(f"Retry delay must be >= 0: {self.retry.retry_delay}")

        # Circuit breaker validation
        if self.circuit_breaker.failure_threshold < 1:
            raise ValueError(f"Failure threshold must be >= 1: {self.circuit_breaker.failure_threshold}")
        if self.circuit_breaker.timeout < 1:
            raise ValueError(f"Circuit breaker timeout must be >= 1: {self.circuit_breaker.timeout}")

        # Rate limit validation
        if self.rate_limit.requests_per_minute < 1:
            raise ValueError(f"Requests per minute must be >= 1: {self.rate_limit.requests_per_minute}")

        # Security validation
        if self.security.max_input_length < 1:
            raise ValueError(f"Max input length must be >= 1: {self.security.max_input_length}")

        logger.info("Configuration validated successfully")
        return True


# Global configuration instance
_config: Optional[SynapticLlamasConfig] = None


def get_config() -> SynapticLlamasConfig:
    """
    Get global configuration instance.

    Returns:
        SynapticLlamasConfig instance
    """
    global _config
    if _config is None:
        _config = SynapticLlamasConfig()
    return _config


def set_config(config: SynapticLlamasConfig):
    """
    Set global configuration instance.

    Args:
        config: Configuration to set
    """
    global _config
    config.validate()
    _config = config


def load_config(config_path: Optional[str] = None) -> SynapticLlamasConfig:
    """
    Load configuration from file or environment.

    Priority: file > environment > defaults

    Args:
        config_path: Optional path to configuration file

    Returns:
        SynapticLlamasConfig instance
    """
    if config_path:
        config = SynapticLlamasConfig.from_file(config_path)
    elif os.getenv('SYNAPTIC_CONFIG_FILE'):
        config = SynapticLlamasConfig.from_file(os.getenv('SYNAPTIC_CONFIG_FILE'))
    else:
        config = SynapticLlamasConfig.from_env()

    config.validate()
    set_config(config)
    return config
