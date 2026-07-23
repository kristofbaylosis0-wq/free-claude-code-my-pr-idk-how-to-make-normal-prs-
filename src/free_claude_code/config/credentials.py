import re
from enum import StrEnum
from typing import Tuple

_KEY_SPLIT_RE = re.compile(r"[,;\s]+")


class CredentialStrategy(StrEnum):
    """Strategy for selecting among multiple API keys."""

    SEQUENTIAL = "sequential"  # Prefer lowest-index key that is enabled and has quota
    ROUND_ROBIN = "round_robin"  # Rotate among enabled keys
    RANDOM = "random"  # Pick a random enabled key


def parse_api_keys(raw: str | None) -> Tuple[str, ...]:
    """Parse comma/semicolon/whitespace-separated API keys; trim and drop empty items.

    Examples:
    - "key1,key2" -> ("key1", "key2")
    - "key1; key2" -> ("key1", "key2")
    - "key1 key2" -> ("key1", "key2")
    """
    if not raw:
        return ()
    keys = tuple(k.strip() for k in _KEY_SPLIT_RE.split(raw) if k.strip())
    return keys


def get_credential_strategy(strategy_str: str | None) -> CredentialStrategy:
    """Parse and validate a credential strategy string.
    
    Defaults to SEQUENTIAL if None or empty.
    """
    if not strategy_str or not strategy_str.strip():
        return CredentialStrategy.SEQUENTIAL
    
    normalized = strategy_str.lower().strip()
    try:
        return CredentialStrategy(normalized)
    except ValueError:
        raise ValueError(
            f"Invalid credential strategy: {strategy_str!r}. "
            f"Must be one of: {', '.join(s.value for s in CredentialStrategy)}"
        )
