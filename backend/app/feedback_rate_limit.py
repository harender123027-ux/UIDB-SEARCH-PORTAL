"""Per-IP sliding window for anonymous POST /api/feedback (in-process; resets on restart)."""

import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_events: dict[str, list[float]] = defaultdict(list)


def clear_state() -> None:
    """Reset counters (for tests)."""
    with _lock:
        _events.clear()


def allow_anonymous_feedback(client_ip: str, max_requests: int, window_sec: int) -> bool:
    if max_requests <= 0:
        return True
    now = time.monotonic()
    with _lock:
        events = _events[client_ip]
        cutoff = now - window_sec
        events[:] = [t for t in events if t > cutoff]
        if len(events) >= max_requests:
            return False
        events.append(now)
        return True
