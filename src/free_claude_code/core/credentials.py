import time
import threading
from typing import List, Optional

class CredentialManager:
    def __init__(self, keys: List[str], policy: str = "rotate") -> None:
        self.keys = keys
        self.policy = policy.lower()
        self.current_index = 0
        self.backoff_until = {}
        self.lock = threading.Lock()

    def get_active_key(self) -> Optional[str]:
        with self.lock:
            if not self.keys:
                return None
            
            # Strict Single-Policy Enforcement
            if self.policy == "single":
                return self.keys[0]
            
            now = time.time()
            for _ in range(len(self.keys)):
                key = self.keys[self.current_index]
                if self.backoff_until.get(key, 0) <= now:
                    return key
                self.current_index = (self.current_index + 1) % len(self.keys)
            
            return self.keys[0]

    def report_error(self, key: str, status_code: Optional[int] = None, is_network_error: bool = False) -> None:
        # Accurate Error Backoff: Ignore HTTP 400 and non-rotatable client errors (4xx except 429)
        if status_code == 400 or (status_code and 400 <= status_code < 500 and status_code != 429):
            return
        
        # Only trigger backoff and rotation on 429 Rate Limits or network dropouts
        if status_code == 429 or is_network_error:
            with self.lock:
                self.backoff_until[key] = time.time() + 60
                if self.policy != "single":
                    self.current_index = (self.current_index + 1) % len(self.keys)
