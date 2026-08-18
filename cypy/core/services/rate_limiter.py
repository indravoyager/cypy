"""
cypy/core/services/rate_limiter.py
✦ Rate Limiter & Time Limit Manager ✦

Modeled after Chisa Translate's rate-limiting architecture:
- Enforces a minimum delay (min_request_delay) between consecutive API requests.
- Handles exponential backoff and countdown logs on 429 Too Many Requests.
- Retries transient network socket/timeout errors up to max_retries.
"""
import math
import re
import sys
import threading
import time
from typing import Callable, Optional, TypeVar

import cypy.core.config as config

T = TypeVar("T")


class ProviderRateLimiter:
    """Thread-safe rate limiter per provider."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_call_time: float = 0.0

    def wait_for_slot(self, provider_name: str = ""):
        """Enforces a minimum delay between consecutive API calls."""
        min_delay = getattr(config, "min_request_delay", 2.0)
        if min_delay <= 0:
            return

        sleep_time = 0.0
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < min_delay:
                sleep_time = min_delay - elapsed
                self._last_call_time = now + sleep_time
            else:
                self._last_call_time = now

        if sleep_time > 0:
            time.sleep(sleep_time)

    def execute_with_retry(
        self,
        api_call: Callable[[], T],
        provider_name: str = "Provider",
        max_retries: int = 3,
        on_wait: Optional[Callable[[str], None]] = None,
    ) -> Optional[T]:
        """
        Executes an API call function with proactive rate limiting delay,
        exponential backoff on 429 errors, and transient timeout retries.
        """
        self.wait_for_slot(provider_name)

        for attempt in range(max_retries):
            if getattr(config, "cancel_translation", False):
                return None

            try:
                with self._lock:
                    self._last_call_time = time.time()
                return api_call()

            except Exception as ex:
                err_str = str(ex).lower()

                # --- 1. Rate Limit Handling (HTTP 429 / Quota exceeded) ---
                if "429" in err_str or "too many requests" in err_str or "rate limit" in err_str or "quota exceeded" in err_str:
                    wait_seconds = 5.0 * (2.0 ** attempt)

                    # Try to parse exact retry seconds from message (e.g. "Please retry in 14.5s")
                    match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str, re.IGNORECASE)
                    if match:
                        try:
                            parsed = float(match.group(1))
                            wait_seconds = parsed + 1.5
                        except ValueError:
                            pass

                    if attempt == max_retries - 1:
                        raise ex

                    total_secs = int(math.ceil(wait_seconds))
                    msg = f"[Rate Limit] Hit rate limit for {provider_name}. Retrying in {total_secs}s..."
                    print(f"\n[!] {msg}")
                    if on_wait:
                        on_wait(msg)

                    for sec in range(total_secs, 0, -1):
                        if getattr(config, "cancel_translation", False):
                            return None
                        time.sleep(1)
                    continue

                # --- 2. Transient Network / Timeout Handling ---
                is_timeout = any(
                    k in err_str for k in ["timeout", "timed out", "connection", "socket", "reset"]
                )
                if is_timeout:
                    if attempt == max_retries - 1:
                        raise ex
                    msg = f"[Network Warning] Attempt {attempt + 1}/{max_retries} for {provider_name} timed out. Retrying in 2s..."
                    print(f"\n[!] {msg}")
                    if on_wait:
                        on_wait(msg)
                    time.sleep(2)
                    continue

                # Non-retryable error or last retry
                if attempt == max_retries - 1:
                    raise ex
                time.sleep(3)

        return None


# Module-level singleton
rate_limiter = ProviderRateLimiter()
