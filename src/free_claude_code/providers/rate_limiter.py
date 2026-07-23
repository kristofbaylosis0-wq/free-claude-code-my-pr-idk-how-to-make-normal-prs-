"""Rate limit and fallback handling for multi-key/multi-provider strategy.

When multiple API keys or fallback providers are configured, the proxy
disables artificial rate limiting and instead uses 429 responses as signals
to rotate to the next credential/provider.
"""

import time
from dataclasses import dataclass, field
from enum import Enum


class CircuitState(Enum):
    """Circuit breaker state for credentials."""

    CLOSED = "closed"  # Ready to use
    OPEN = "open"  # Recently returned 429, waiting before retry
    HALF_OPEN = "half_open"  # Testing if credential is back


@dataclass
class CredentialCircuitBreaker:
    """Per-credential circuit breaker to track exhaustion and backoff."""

    credential_id: str  # api_key or provider_id
    state: CircuitState = CircuitState.CLOSED
    last_429_at: float = 0.0
    backoff_seconds: float = 5.0
    consecutive_failures: int = 0
    max_consecutive_failures: int = 5

    @property
    def is_available(self) -> bool:\n        \"\"\"Check if credential is available now.\"\"\"\n        if self.state == CircuitState.CLOSED:\n            return True\n        if self.state == CircuitState.HALF_OPEN:\n            # Allow one attempt to test recovery\n            return True\n        # OPEN: check if backoff expired\n        elapsed = time.time() - self.last_429_at\n        if elapsed >= self.backoff_seconds:\n            self.state = CircuitState.HALF_OPEN\n            return True\n        return False\n\n    def record_429(self) -> None:\n        \"\"\"Record a rate limit error.\"\"\"\n        self.state = CircuitState.OPEN\n        self.last_429_at = time.time()\n        self.consecutive_failures += 1\n        # Exponential backoff: 5s, 10s, 20s, 40s, 80s\n        self.backoff_seconds = min(5.0 * (2 ** (self.consecutive_failures - 1)), 300.0)\n\n    def record_success(self) -> None:\n        \"\"\"Record a successful request.\"\"\"\n        self.state = CircuitState.CLOSED\n        self.consecutive_failures = 0\n        self.backoff_seconds = 5.0\n\n    def is_permanently_exhausted(self) -> bool:\n        \"\"\"Check if credential has exceeded max retries.\"\"\"\n        return self.consecutive_failures >= self.max_consecutive_failures\n\n\n@dataclass\nclass RotationState:\n    \"\"\"Mutable state for credential/provider rotation.\"\"\"\n\n    current_index: int = 0\n    circuit_breakers: dict[str, CredentialCircuitBreaker] = field(\n        default_factory=dict\n    )\n    last_rotation_at: float = 0.0\n\n    def should_rotate_on_429(\n        self, credential_id: str, credentials: tuple[str, ...]\n    ) -> bool:\n        \"\"\"Check if we should try the next credential after 429.\"\"\"\n        if not credentials or len(credentials) <= 1:\n            # Single credential: no rotation possible\n            return False\n        # Only rotate if this credential is exhausted\n        breaker = self.circuit_breakers.get(\n            credential_id, CredentialCircuitBreaker(credential_id)\n        )\n        return breaker.consecutive_failures > 0\n\n    def get_next_available_credential(\n        self, credentials: tuple[str, ...], strategy: str\n    ) -> str | None:\n        \"\"\"Find the next available credential based on strategy.\n\n        Returns None if all credentials are permanently exhausted.\n        \"\"\"\n        if not credentials:\n            return None\n\n        available = [\n            cred\n            for cred in credentials\n            if not self.circuit_breakers.get(\n                cred, CredentialCircuitBreaker(cred)\n            ).is_permanently_exhausted()\n        ]\n\n        if not available:\n            return None\n\n        if strategy == \"round_robin\":\n            # Rotate to next available\n            for offset in range(1, len(credentials)):\n                idx = (self.current_index + offset) % len(credentials)\n                cred = credentials[idx]\n                if cred in available:\n                    self.current_index = idx\n                    self.last_rotation_at = time.time()\n                    return cred\n        elif strategy == \"random\":\n            import random\n\n            return random.choice(available)\n        else:  # sequential (default)\n            # Prefer first available in order\n            for cred in available:\n                return cred\n\n        return available[0] if available else None\n\n    def record_429_for_credential(self, credential_id: str) -> None:\n        \"\"\"Mark credential as rate-limited.\"\"\"\n        if credential_id not in self.circuit_breakers:\n            self.circuit_breakers[credential_id] = CredentialCircuitBreaker(\n                credential_id\n            )\n        self.circuit_breakers[credential_id].record_429()\n\n    def record_success_for_credential(self, credential_id: str) -> None:\n        \"\"\"Clear rate-limit flag for credential.\"\"\"\n        if credential_id not in self.circuit_breakers:\n            self.circuit_breakers[credential_id] = CredentialCircuitBreaker(\n                credential_id\n            )\n        self.circuit_breakers[credential_id].record_success()\n\n\ndef should_disable_rate_limiting(api_keys: tuple[str, ...], fallback_providers: tuple[str, ...]) -> bool:\n    \"\"\"Determine if artificial rate limiting should be disabled.\n\n    When multi-key or multi-provider fallback is configured, disable\n    artificial rate limiting and let 429 responses drive rotation.\n    \"\"\"\n    has_multiple_keys = len(api_keys) > 1\n    has_fallback = len(fallback_providers) > 1\n    return has_multiple_keys or has_fallback\n"