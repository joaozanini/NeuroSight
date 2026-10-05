"""Limite de tentativas em memória (por processo), contra adivinhação de senha no login.

Conta só as falhas, numa janela deslizante. Como fica em memória, cada worker conta as suas; a
partir da Fase 8 a API roda com um worker só.
"""
import threading
import time
from collections import deque


class FailureLimiter:
    def __init__(self, max_failures: int, window_seconds: float):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        q = self._failures.setdefault(key, deque())
        while q and q[0] <= now - self.window:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        with self._lock:
            q = self._recent(key, time.monotonic())
            if not q:
                self._failures.pop(key, None)
            return len(q) >= self.max_failures

    def fail(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._recent(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


# 10 senhas erradas para o mesmo e-mail a partir do mesmo IP em 15 minutos bloqueiam até a
# janela andar.
login_limiter = FailureLimiter(max_failures=10, window_seconds=15 * 60)
