"""Error handling utilities with retry logic and circuit breaker pattern."""
import time
import logging
import functools
from typing import Callable, Optional, Type, Tuple, Any
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by stopping requests to failing services.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting recovery (HALF_OPEN)
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
        return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return False
        return datetime.now() - self._last_failure_time > timedelta(seconds=self.timeout)

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"Circuit breaker is OPEN. Last failure: {self._last_failure_time}"
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful call."""
        self._failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            logger.info("Circuit breaker CLOSED after successful recovery")

    def _on_failure(self):
        """Handle failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker OPENED after {self._failure_count} failures. "
                f"Will retry in {self.timeout}s"
            )

    def reset(self):
        """Manually reset circuit breaker."""
        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED
        logger.info("Circuit breaker manually reset to CLOSED")

    def __repr__(self):
        return (
            f"CircuitBreaker(state={self.state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )


def circuit_breaker(
    failure_threshold: int = 5,
    timeout: int = 60,
    expected_exception: Type[Exception] = Exception
):
    """
    Circuit breaker decorator.

    Usage:
        @circuit_breaker(failure_threshold=3, timeout=30)
        def call_external_api():
            ...

    Args:
        failure_threshold: Number of failures before opening circuit
        timeout: Seconds to wait before attempting recovery
        expected_exception: Exception type to catch
    """
    breaker = CircuitBreaker(failure_threshold, timeout, expected_exception)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        wrapper.circuit_breaker = breaker
        return wrapper
    return decorator


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exponential_backoff: bool = True,
    backoff_multiplier: float = 2.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Retry decorator with exponential backoff.

    Usage:
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def unstable_function():
            ...

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        exponential_backoff: Whether to use exponential backoff
        backoff_multiplier: Multiplier for exponential backoff
        max_delay: Maximum delay between retries
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    time.sleep(delay)

                    if exponential_backoff:
                        delay = min(delay * backoff_multiplier, max_delay)

            raise last_exception

        return wrapper
    return decorator


def timeout_handler(timeout_seconds: int):
    """
    Timeout decorator using signal (Unix only).

    Usage:
        @timeout_handler(30)
        def long_running_function():
            ...

    Args:
        timeout_seconds: Timeout in seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal

            def timeout_signal_handler(signum, frame):
                raise TimeoutError(f"{func.__name__} timed out after {timeout_seconds}s")

            # Set the signal handler and alarm
            old_handler = signal.signal(signal.SIGALRM, timeout_signal_handler)
            signal.alarm(timeout_seconds)

            try:
                result = func(*args, **kwargs)
            finally:
                # Restore the old signal handler and cancel the alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result
        return wrapper
    return decorator


class RateLimiter:
    """
    Token bucket rate limiter.

    Limits the rate of requests to prevent overwhelming services.
    """

    def __init__(self, requests_per_minute: int = 60, burst_size: Optional[int] = None):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute
            burst_size: Maximum burst size (defaults to requests_per_minute)
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size or requests_per_minute
        self.tokens = float(self.burst_size)
        self.last_update = time.time()
        self.rate = requests_per_minute / 60.0  # Tokens per second

    def _refill_tokens(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(
            self.burst_size,
            self.tokens + elapsed * self.rate
        )
        self.last_update = now

    def acquire(self, tokens: int = 1, block: bool = True) -> bool:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire
            block: Whether to block until tokens are available

        Returns:
            True if tokens acquired, False otherwise
        """
        while True:
            self._refill_tokens()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            if not block:
                return False

            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.rate
            time.sleep(min(wait_time, 1.0))  # Sleep max 1 second at a time

    def __call__(self, func: Callable) -> Callable:
        """Use as decorator."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self.acquire()
            return func(*args, **kwargs)
        return wrapper


def rate_limit(requests_per_minute: int = 60, burst_size: Optional[int] = None):
    """
    Rate limiting decorator.

    Usage:
        @rate_limit(requests_per_minute=30)
        def api_call():
            ...

    Args:
        requests_per_minute: Maximum requests per minute
        burst_size: Maximum burst size
    """
    limiter = RateLimiter(requests_per_minute, burst_size)
    return limiter


class ErrorAggregator:
    """
    Aggregate and track errors across multiple operations.
    """

    def __init__(self, max_errors: int = 100):
        """
        Initialize error aggregator.

        Args:
            max_errors: Maximum number of errors to track
        """
        self.max_errors = max_errors
        self.errors = []

    def add_error(self, error: Exception, context: Optional[str] = None):
        """
        Add error to aggregator.

        Args:
            error: Exception that occurred
            context: Optional context string
        """
        error_info = {
            "timestamp": datetime.now(),
            "error": error,
            "type": type(error).__name__,
            "message": str(error),
            "context": context
        }

        self.errors.append(error_info)

        # Keep only most recent errors
        if len(self.errors) > self.max_errors:
            self.errors = self.errors[-self.max_errors:]

        logger.error(f"Error recorded: {error_info['type']} - {error_info['message']}")

    def get_error_summary(self) -> dict:
        """
        Get summary of errors.

        Returns:
            Dictionary with error statistics
        """
        if not self.errors:
            return {"total_errors": 0, "error_types": {}}

        error_types = {}
        for error_info in self.errors:
            error_type = error_info["type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "total_errors": len(self.errors),
            "error_types": error_types,
            "first_error": self.errors[0]["timestamp"],
            "last_error": self.errors[-1]["timestamp"],
            "most_common": max(error_types.items(), key=lambda x: x[1])[0] if error_types else None
        }

    def clear(self):
        """Clear all recorded errors."""
        self.errors.clear()
        logger.info("Error aggregator cleared")

    def __len__(self):
        return len(self.errors)

    def __repr__(self):
        summary = self.get_error_summary()
        return f"ErrorAggregator({summary['total_errors']} errors)"
