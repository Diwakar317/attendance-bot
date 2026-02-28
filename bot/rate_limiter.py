"""
Simple in-memory rate limiter using a sliding-window approach.
Thread-safe via threading.Lock.
"""

import time
import threading
from collections import defaultdict
from bot.logging_config import get_security_logger

sec_log = get_security_logger()


class RateLimiter:
    """
    Track events per key within a sliding window.
    Example: RateLimiter(max_attempts=5, window_seconds=300)
    allows 5 events per key in any 300-second window.
    """

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _cleanup(self, key: str) -> None:
        cutoff = time.monotonic() - self.window
        self._store[key] = [t for t in self._store[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        """Return True if the action is still within rate limits."""
        with self._lock:
            self._cleanup(key)
            return len(self._store[key]) < self.max_attempts

    def record(self, key: str) -> None:
        """Record an event for the given key."""
        with self._lock:
            self._cleanup(key)
            self._store[key].append(time.monotonic())

    def hit(self, key: str) -> bool:
        """
        Record an event and return True if still within limits,
        False if the limit has been exceeded.
        """
        with self._lock:
            self._cleanup(key)
            if len(self._store[key]) >= self.max_attempts:
                return False
            self._store[key].append(time.monotonic())
            return True

    def remaining(self, key: str) -> int:
        with self._lock:
            self._cleanup(key)
            return max(0, self.max_attempts - len(self._store[key]))


# ── Pre-configured limiters ─────────────────────────────────────

# Login: 5 attempts per IP per 5 minutes
login_limiter = RateLimiter(max_attempts=5, window_seconds=300)

# Face verification: 5 attempts per user per 10 minutes
face_verify_limiter = RateLimiter(max_attempts=5, window_seconds=600)

# Check-in: 3 attempts per user per 5 minutes
checkin_limiter = RateLimiter(max_attempts=3, window_seconds=300)
