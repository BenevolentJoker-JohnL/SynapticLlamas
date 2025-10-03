"""Input validation and sanitization utilities."""
import re
import logging
from typing import Optional, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_url(url: str, allowed_protocols: Optional[List[str]] = None, require_https: bool = False) -> bool:
    """
    Validate URL format and protocol.

    Args:
        url: URL to validate
        allowed_protocols: List of allowed protocols (default: ['http', 'https'])
        require_https: Whether to require HTTPS protocol

    Returns:
        True if valid

    Raises:
        ValidationError: If URL is invalid
    """
    if not url:
        raise ValidationError("URL cannot be empty")

    if not isinstance(url, str):
        raise ValidationError(f"URL must be string, got {type(url)}")

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValidationError(f"Invalid URL format: {e}")

    if not parsed.scheme:
        raise ValidationError("URL must include protocol (http:// or https://)")

    if not parsed.netloc:
        raise ValidationError("URL must include host")

    allowed_protocols = allowed_protocols or ['http', 'https']
    if parsed.scheme not in allowed_protocols:
        raise ValidationError(
            f"Protocol '{parsed.scheme}' not allowed. Allowed: {allowed_protocols}"
        )

    if require_https and parsed.scheme != 'https':
        raise ValidationError("HTTPS protocol required")

    logger.debug(f"URL validated: {url}")
    return True


def validate_ip_address(ip: str) -> bool:
    """
    Validate IP address format.

    Args:
        ip: IP address to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If IP address is invalid
    """
    if not ip:
        raise ValidationError("IP address cannot be empty")

    # IPv4 pattern
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'

    if not re.match(ipv4_pattern, ip):
        raise ValidationError(f"Invalid IP address format: {ip}")

    # Validate octets
    octets = ip.split('.')
    for octet in octets:
        if not 0 <= int(octet) <= 255:
            raise ValidationError(f"Invalid IP address octet: {octet}")

    logger.debug(f"IP address validated: {ip}")
    return True


def validate_port(port: int) -> bool:
    """
    Validate port number.

    Args:
        port: Port number to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If port is invalid
    """
    if not isinstance(port, int):
        raise ValidationError(f"Port must be integer, got {type(port)}")

    if not 1 <= port <= 65535:
        raise ValidationError(f"Port must be between 1 and 65535, got {port}")

    logger.debug(f"Port validated: {port}")
    return True


def validate_cidr(cidr: str) -> bool:
    """
    Validate CIDR notation (e.g., 192.168.1.0/24).

    Args:
        cidr: CIDR notation to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If CIDR is invalid
    """
    if not cidr:
        raise ValidationError("CIDR cannot be empty")

    if '/' not in cidr:
        raise ValidationError("CIDR must include subnet mask (e.g., 192.168.1.0/24)")

    try:
        ip, mask = cidr.split('/')
        validate_ip_address(ip)
        mask_int = int(mask)

        if not 0 <= mask_int <= 32:
            raise ValidationError(f"Subnet mask must be between 0 and 32, got {mask_int}")

    except ValueError as e:
        raise ValidationError(f"Invalid CIDR format: {e}")

    logger.debug(f"CIDR validated: {cidr}")
    return True


def sanitize_input(text: str, max_length: int = 100000) -> str:
    """
    Sanitize user input text.

    Args:
        text: Text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text

    Raises:
        ValidationError: If input is invalid
    """
    if not isinstance(text, str):
        raise ValidationError(f"Input must be string, got {type(text)}")

    if len(text) > max_length:
        raise ValidationError(
            f"Input exceeds maximum length of {max_length} characters "
            f"(got {len(text)})"
        )

    # Remove null bytes
    text = text.replace('\x00', '')

    # Remove control characters except common whitespace
    text = ''.join(
        char for char in text
        if char >= ' ' or char in '\n\r\t'
    )

    # Normalize whitespace
    text = ' '.join(text.split())

    logger.debug(f"Input sanitized ({len(text)} chars)")
    return text


def validate_model_name(model: str) -> bool:
    """
    Validate Ollama model name.

    Args:
        model: Model name to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If model name is invalid
    """
    if not model:
        raise ValidationError("Model name cannot be empty")

    if not isinstance(model, str):
        raise ValidationError(f"Model name must be string, got {type(model)}")

    # Allow alphanumeric, hyphens, underscores, dots, and colons
    if not re.match(r'^[a-zA-Z0-9\-_.:\s]+$', model):
        raise ValidationError(
            f"Invalid model name '{model}'. "
            "Must contain only alphanumeric characters, hyphens, underscores, dots, colons, and spaces"
        )

    logger.debug(f"Model name validated: {model}")
    return True


def validate_strategy(strategy: str, valid_strategies: List[str]) -> bool:
    """
    Validate routing strategy name.

    Args:
        strategy: Strategy name to validate
        valid_strategies: List of valid strategy names

    Returns:
        True if valid

    Raises:
        ValidationError: If strategy is invalid
    """
    if not strategy:
        raise ValidationError("Strategy cannot be empty")

    if strategy not in valid_strategies:
        raise ValidationError(
            f"Invalid strategy '{strategy}'. Valid strategies: {valid_strategies}"
        )

    logger.debug(f"Strategy validated: {strategy}")
    return True


def validate_file_path(path: str, must_exist: bool = False) -> bool:
    """
    Validate file path.

    Args:
        path: File path to validate
        must_exist: Whether file must exist

    Returns:
        True if valid

    Raises:
        ValidationError: If path is invalid
    """
    if not path:
        raise ValidationError("File path cannot be empty")

    if not isinstance(path, str):
        raise ValidationError(f"File path must be string, got {type(path)}")

    # Check for path traversal attempts
    if '..' in path:
        raise ValidationError("Path traversal not allowed")

    # Check for null bytes
    if '\x00' in path:
        raise ValidationError("Null bytes not allowed in path")

    if must_exist:
        from pathlib import Path
        if not Path(path).exists():
            raise ValidationError(f"File does not exist: {path}")

    logger.debug(f"File path validated: {path}")
    return True


def validate_config_dict(config: dict, required_keys: List[str]) -> bool:
    """
    Validate configuration dictionary.

    Args:
        config: Configuration dictionary to validate
        required_keys: List of required keys

    Returns:
        True if valid

    Raises:
        ValidationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ValidationError(f"Config must be dictionary, got {type(config)}")

    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValidationError(f"Missing required configuration keys: {missing_keys}")

    logger.debug(f"Configuration validated ({len(config)} keys)")
    return True


class InputValidator:
    """
    Comprehensive input validator with caching.
    """

    def __init__(self, max_length: int = 100000, require_https: bool = False):
        """
        Initialize validator.

        Args:
            max_length: Maximum input length
            require_https: Whether to require HTTPS for URLs
        """
        self.max_length = max_length
        self.require_https = require_https

    def validate_query(self, query: str) -> str:
        """
        Validate and sanitize user query.

        Args:
            query: User query to validate

        Returns:
            Sanitized query

        Raises:
            ValidationError: If query is invalid
        """
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty")

        return sanitize_input(query, self.max_length)

    def validate_node_url(self, url: str) -> bool:
        """
        Validate Ollama node URL.

        Args:
            url: Node URL to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If URL is invalid
        """
        return validate_url(
            url,
            allowed_protocols=['http', 'https'],
            require_https=self.require_https
        )

    def validate_discovery_range(self, cidr: str) -> bool:
        """
        Validate network discovery range.

        Args:
            cidr: CIDR notation to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If CIDR is invalid
        """
        return validate_cidr(cidr)

    def validate_all(self, **kwargs) -> dict:
        """
        Validate multiple inputs at once.

        Args:
            **kwargs: Key-value pairs to validate

        Returns:
            Dictionary of validated values

        Raises:
            ValidationError: If any validation fails
        """
        validated = {}

        for key, value in kwargs.items():
            if key == 'url':
                self.validate_node_url(value)
            elif key == 'port':
                validate_port(value)
            elif key == 'model':
                validate_model_name(value)
            elif key == 'query':
                value = self.validate_query(value)
            elif key == 'cidr':
                self.validate_discovery_range(value)
            elif key == 'path':
                validate_file_path(value)

            validated[key] = value

        return validated
