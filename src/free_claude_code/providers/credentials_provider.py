"""Rotating credential provider with simple backoff and disabled-state tracking.

This is intentionally lightweight and thread-safe for sync usage. If providers
call this from async code, wrap accesses with an executor or add an async
variant that uses asyncio.Lock.
"""
import time
import random
import threading
from typing import Sequence, Optional, Dict


class RotatingCredentialProvider:
    """Provide API keys in round-robin fashion and allow marking keys as failed.

    - next_key() returns the next enabled key or None if none are available.
    - mark_failure() disables a key for an exponentially growing backoff period.
    - mark_success() clears failure state for a key.

    This is intentionally conservative: failures are per-key and shared across
    all users of the same RotatingCredentialProvider instance.
    """

    def __init__(self, keys: Sequence[str]):
        self._keys = [k for k in keys if k]
        self._n = len(self._keys)
        self._idx = 0
        self._lock = threading.Lock()
        # disabled_until: key -> unix timestamp until which the key is disabled
        self._disabled_until: Dict[str, float] = {}
        # failure counts to grow backoff per-key
        self._fail_counts: Dict[str, int] = {}

    def _is_enabled(self, key: str) -> bool:
        until = self._disabled_until.get(key)
        return not until or time.time() >= until

    def next_key(self) -> Optional[str]:
        """Return the next enabled key (round-robin) or None if none available."""
        with self._lock:
            if not self._keys:
                return None
            checked = 0
            while checked < self._n:
                key = self._keys[self._idx % self._n]
                self._idx += 1
                checked += 1
                if self._is_enabled(key):
                    return key
            return None

    def mark_failure(self, key: str, retry_after_seconds: Optional[int] = None) -> None:
        """Mark a key as failed. If retry_after_seconds is None an exponential backoff is used."""
        with self._lock:
            count = self._fail_counts.get(key, 0) + 1
            self._fail_counts[key] = count
            if retry_after_seconds is None:
                # exponential backoff: 2^(count) seconds, capped to 1 hour
                base = min(3600, 2 ** min(count, 10))
                # small jitter (0-10%) to avoid thundering herd
                jitter = random.uniform(0, base * 0.1)
                retry_after_seconds = int(base + jitter)
            self._disabled_until[key] = time.time() + float(max(1, int(retry_after_seconds)))

    def mark_success(self, key: str) -> None:
        with self._lock:
            self._fail_counts.pop(key, None)
            self._disabled_until.pop(key, None)
