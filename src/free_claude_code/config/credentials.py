import re
from typing import Tuple

_KEY_SPLIT_RE = re.compile(r"[,;\s]+")


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
