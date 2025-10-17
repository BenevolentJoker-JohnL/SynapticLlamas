"""
Authentication and authorization for SOLLOL.

Provides API key-based authentication and role-based access control.
"""
from typing import Optional, List
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from dataclasses import dataclass
import hashlib
import secrets

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class APIKey:
    """API key with permissions."""
    key_hash: str
    name: str
    permissions: List[str]
    rate_limit: int = 1000  # requests per hour


class AuthManager:
    """
    Authentication and authorization manager.

    Features:
    - API key-based authentication
    - Role-based permissions
    - Rate limiting per key
    - Key rotation support
    """

    def __init__(self):
        self.api_keys: dict[str, APIKey] = {}
        self.request_counts: dict[str, int] = {}

    def create_api_key(
        self,
        name: str,
        permissions: List[str],
        rate_limit: int = 1000
    ) -> str:
        """
        Create a new API key.

        Args:
            name: Key identifier/description
            permissions: List of allowed permissions
            rate_limit: Max requests per hour

        Returns:
            Generated API key (only shown once!)
        """
        # Generate secure random key
        raw_key = secrets.token_urlsafe(32)

        # Store hash, not the key itself
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        self.api_keys[key_hash] = APIKey(
            key_hash=key_hash,
            name=name,
            permissions=permissions,
            rate_limit=rate_limit
        )

        return raw_key

    def verify_api_key(self, api_key: str) -> Optional[APIKey]:
        """
        Verify API key and return associated permissions.

        Args:
            api_key: Raw API key from request

        Returns:
            APIKey object if valid, None otherwise
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return self.api_keys.get(key_hash)

    def check_permission(self, api_key: str, required_permission: str) -> bool:
        """
        Check if API key has required permission.

        Args:
            api_key: Raw API key
            required_permission: Permission to check

        Returns:
            True if authorized, False otherwise
        """
        key_obj = self.verify_api_key(api_key)
        if not key_obj:
            return False

        # Admin permission grants all access
        if "admin" in key_obj.permissions:
            return True

        return required_permission in key_obj.permissions

    def check_rate_limit(self, api_key: str) -> bool:
        """
        Check if API key is within rate limit.

        Args:
            api_key: Raw API key

        Returns:
            True if within limit, False if exceeded
        """
        key_obj = self.verify_api_key(api_key)
        if not key_obj:
            return False

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        current_count = self.request_counts.get(key_hash, 0)

        if current_count >= key_obj.rate_limit:
            return False

        self.request_counts[key_hash] = current_count + 1
        return True

    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key.

        Args:
            api_key: Raw API key to revoke

        Returns:
            True if revoked, False if not found
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        if key_hash in self.api_keys:
            del self.api_keys[key_hash]
            if key_hash in self.request_counts:
                del self.request_counts[key_hash]
            return True
        return False


# Global auth manager instance
_auth_manager = AuthManager()


def get_auth_manager() -> AuthManager:
    """Get global auth manager instance."""
    return _auth_manager


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> APIKey:
    """
    FastAPI dependency for API key verification.

    Usage:
        @app.get("/protected")
        async def protected_endpoint(key: APIKey = Depends(verify_api_key)):
            return {"message": "Authorized"}

    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include X-API-Key header."
        )

    auth = get_auth_manager()
    key_obj = auth.verify_api_key(api_key)

    if not key_obj:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    # Check rate limit
    if not auth.check_rate_limit(api_key):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )

    return key_obj


async def require_permission(permission: str):
    """
    FastAPI dependency for permission checking.

    Usage:
        @app.post("/admin/action")
        async def admin_action(
            key: APIKey = Depends(verify_api_key),
            _: None = Depends(require_permission("admin"))
        ):
            return {"message": "Admin action executed"}
    """
    async def check(api_key: str = Security(API_KEY_HEADER)):
        key_obj = await verify_api_key(api_key)

        if "admin" not in key_obj.permissions and permission not in key_obj.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Missing required permission: {permission}"
            )

    return check


# Permission constants
PERM_CHAT = "chat"
PERM_EMBED = "embed"
PERM_BATCH = "batch"
PERM_STATS = "stats"
PERM_HEALTH = "health"
PERM_ADMIN = "admin"
