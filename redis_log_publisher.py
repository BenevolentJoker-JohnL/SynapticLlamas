"""
Redis Log Publisher for llama.cpp Live Logs

Publishes llama.cpp coordinator and RPC backend logs to Redis in real-time,
enabling external monitoring systems to consume logs via Redis pub/sub.

Channels:
    synapticllamas:llama_cpp:logs - All llama.cpp related logs
    synapticllamas:llama_cpp:coordinator - Coordinator-specific events
    synapticllamas:llama_cpp:rpc_backends - RPC backend events
    synapticllamas:llama_cpp:metrics - Performance metrics
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import redis
from redis import Redis, ConnectionPool

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComponentType(str, Enum):
    """llama.cpp component types."""
    COORDINATOR = "coordinator"
    RPC_BACKEND = "rpc_backend"
    SYSTEM = "system"
    MODEL = "model"


@dataclass
class LlamaCppLogEvent:
    """Structured log event for llama.cpp operations."""
    timestamp: float
    component: str  # ComponentType
    level: str  # LogLevel
    message: str
    event_type: str  # e.g., "start", "stop", "model_load", "connect", "error"
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            k: v for k, v in asdict(self).items()
            if v is not None
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class RedisLogPublisher:
    """
    Publishes llama.cpp logs to Redis pub/sub channels.

    Usage:
        publisher = RedisLogPublisher(
            host="localhost",
            port=6379,
            db=0
        )

        # Publish a log event
        await publisher.publish_log(
            component=ComponentType.COORDINATOR,
            level=LogLevel.INFO,
            message="Coordinator started",
            event_type="start",
            details={"port": 8080, "backends": 2}
        )

        # Publish raw coordinator stdout
        await publisher.publish_raw_log(
            "llama_print_timings: eval time = 1234.56 ms"
        )
    """

    # Channel names
    CHANNEL_ALL_LOGS = "synapticllamas:llama_cpp:logs"
    CHANNEL_COORDINATOR = "synapticllamas:llama_cpp:coordinator"
    CHANNEL_RPC_BACKENDS = "synapticllamas:llama_cpp:rpc_backends"
    CHANNEL_METRICS = "synapticllamas:llama_cpp:metrics"
    CHANNEL_RAW_LOGS = "synapticllamas:llama_cpp:raw"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        enabled: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize Redis log publisher.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (if required)
            enabled: Whether to enable publishing (can be disabled for testing)
            max_retries: Maximum connection retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.enabled = enabled
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.redis_client: Optional[Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None
        self.is_connected = False

        # Statistics
        self.total_published = 0
        self.failed_publishes = 0
        self.last_error: Optional[str] = None

        # Connect on initialization
        if self.enabled:
            self._connect()

    def _connect(self) -> bool:
        """
        Connect to Redis.

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            # Create connection pool
            self.connection_pool = ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=10,
                decode_responses=True  # Auto-decode bytes to strings
            )

            # Create Redis client
            self.redis_client = Redis(connection_pool=self.connection_pool)

            # Test connection
            self.redis_client.ping()

            self.is_connected = True
            logger.info(f"✅ Redis log publisher connected to {self.host}:{self.port}")
            return True

        except Exception as e:
            self.is_connected = False
            self.last_error = str(e)
            logger.warning(f"Failed to connect to Redis: {e}")
            return False

    def _ensure_connected(self) -> bool:
        """Ensure Redis connection is active, reconnect if needed."""
        if not self.enabled:
            return False

        if self.is_connected and self.redis_client:
            try:
                # Quick ping to verify connection
                self.redis_client.ping()
                return True
            except Exception:
                self.is_connected = False

        # Try to reconnect
        for attempt in range(self.max_retries):
            if self._connect():
                return True
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        return False

    def publish_log(
        self,
        component: ComponentType,
        level: LogLevel,
        message: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Publish a structured log event.

        Args:
            component: Component that generated the log
            level: Log severity level
            message: Human-readable message
            event_type: Event type identifier
            details: Additional structured data
            timestamp: Event timestamp (defaults to current time)

        Returns:
            True if published successfully, False otherwise
        """
        if not self._ensure_connected():
            self.failed_publishes += 1
            return False

        try:
            # Create log event
            event = LlamaCppLogEvent(
                timestamp=timestamp or time.time(),
                component=component.value if isinstance(component, ComponentType) else component,
                level=level.value if isinstance(level, LogLevel) else level,
                message=message,
                event_type=event_type,
                details=details
            )

            # Serialize to JSON
            log_json = event.to_json()

            # Publish to main channel
            self.redis_client.publish(self.CHANNEL_ALL_LOGS, log_json)

            # Publish to component-specific channel
            if component == ComponentType.COORDINATOR:
                self.redis_client.publish(self.CHANNEL_COORDINATOR, log_json)
            elif component == ComponentType.RPC_BACKEND:
                self.redis_client.publish(self.CHANNEL_RPC_BACKENDS, log_json)

            # Publish metrics to metrics channel if it's a metrics event
            if event_type in ["metric", "performance", "stats"]:
                self.redis_client.publish(self.CHANNEL_METRICS, log_json)

            self.total_published += 1
            return True

        except Exception as e:
            self.failed_publishes += 1
            self.last_error = str(e)
            logger.error(f"Failed to publish log to Redis: {e}")
            self.is_connected = False
            return False

    def publish_raw_log(
        self,
        log_line: str,
        source: str = "coordinator",
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Publish raw log line from llama.cpp stdout/stderr.

        Args:
            log_line: Raw log line from llama.cpp
            source: Log source ("coordinator" or backend address)
            timestamp: Log timestamp (defaults to current time)

        Returns:
            True if published successfully, False otherwise
        """
        if not self._ensure_connected():
            self.failed_publishes += 1
            return False

        try:
            # Create raw log entry
            raw_log = {
                "timestamp": timestamp or time.time(),
                "source": source,
                "line": log_line.strip()
            }

            # Publish to raw logs channel
            self.redis_client.publish(
                self.CHANNEL_RAW_LOGS,
                json.dumps(raw_log)
            )

            self.total_published += 1
            return True

        except Exception as e:
            self.failed_publishes += 1
            self.last_error = str(e)
            logger.error(f"Failed to publish raw log to Redis: {e}")
            self.is_connected = False
            return False

    def publish_coordinator_start(
        self,
        model_path: str,
        port: int,
        rpc_backends: List[str],
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish coordinator start event."""
        return self.publish_log(
            component=ComponentType.COORDINATOR,
            level=LogLevel.INFO,
            message=f"llama.cpp coordinator started on port {port}",
            event_type="start",
            details={
                "model_path": model_path,
                "port": port,
                "rpc_backends": rpc_backends,
                "backend_count": len(rpc_backends),
                **(details or {})
            }
        )

    def publish_coordinator_stop(
        self,
        reason: Optional[str] = None
    ) -> bool:
        """Publish coordinator stop event."""
        return self.publish_log(
            component=ComponentType.COORDINATOR,
            level=LogLevel.WARNING,
            message="llama.cpp coordinator stopped",
            event_type="stop",
            details={"reason": reason} if reason else None
        )

    def publish_model_load(
        self,
        model_name: str,
        model_path: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish model load event."""
        return self.publish_log(
            component=ComponentType.MODEL,
            level=LogLevel.INFO,
            message=f"Model loaded: {model_name}",
            event_type="model_load",
            details={
                "model_name": model_name,
                "model_path": model_path,
                **(details or {})
            }
        )

    def publish_rpc_backend_connect(
        self,
        backend_address: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish RPC backend connection event."""
        return self.publish_log(
            component=ComponentType.RPC_BACKEND,
            level=LogLevel.INFO,
            message=f"RPC backend connected: {backend_address}",
            event_type="connect",
            details={
                "backend": backend_address,
                **(details or {})
            }
        )

    def publish_rpc_backend_disconnect(
        self,
        backend_address: str,
        reason: Optional[str] = None
    ) -> bool:
        """Publish RPC backend disconnection event."""
        return self.publish_log(
            component=ComponentType.RPC_BACKEND,
            level=LogLevel.WARNING,
            message=f"RPC backend disconnected: {backend_address}",
            event_type="disconnect",
            details={
                "backend": backend_address,
                "reason": reason
            } if reason else {"backend": backend_address}
        )

    def publish_error(
        self,
        component: ComponentType,
        error_message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish error event."""
        return self.publish_log(
            component=component,
            level=LogLevel.ERROR,
            message=error_message,
            event_type="error",
            details=details
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics."""
        return {
            "enabled": self.enabled,
            "connected": self.is_connected,
            "host": self.host,
            "port": self.port,
            "total_published": self.total_published,
            "failed_publishes": self.failed_publishes,
            "success_rate": (
                self.total_published / (self.total_published + self.failed_publishes)
                if (self.total_published + self.failed_publishes) > 0
                else 1.0
            ),
            "last_error": self.last_error
        }

    def close(self):
        """Close Redis connection."""
        if self.redis_client:
            try:
                self.redis_client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")

        if self.connection_pool:
            try:
                self.connection_pool.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting connection pool: {e}")

        self.is_connected = False
        logger.info("Redis log publisher closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Global singleton instance
_global_publisher: Optional[RedisLogPublisher] = None


def get_global_publisher() -> Optional[RedisLogPublisher]:
    """Get the global Redis log publisher instance."""
    return _global_publisher


def initialize_global_publisher(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
    enabled: bool = True
) -> RedisLogPublisher:
    """
    Initialize the global Redis log publisher.

    Args:
        host: Redis host
        port: Redis port
        db: Redis database number
        password: Redis password
        enabled: Whether to enable publishing

    Returns:
        RedisLogPublisher instance
    """
    global _global_publisher

    if _global_publisher is not None:
        logger.warning("Global Redis publisher already initialized")
        return _global_publisher

    _global_publisher = RedisLogPublisher(
        host=host,
        port=port,
        db=db,
        password=password,
        enabled=enabled
    )

    return _global_publisher


def shutdown_global_publisher():
    """Shutdown the global Redis log publisher."""
    global _global_publisher

    if _global_publisher is not None:
        _global_publisher.close()
        _global_publisher = None
