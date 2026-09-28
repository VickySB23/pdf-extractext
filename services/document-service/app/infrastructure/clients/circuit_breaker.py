"""Circuit Breaker mínimo (patrón del cap. 2.5.1 del libro): cerrado -> abierto -> semi-abierto."""
import time
from collections.abc import Callable


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if self._clock() - self._opened_at >= self.reset_timeout:
            return "half_open"
        return "open"

    def before_call(self) -> None:
        if self.state == "open":
            raise CircuitOpenError("Circuito abierto: el servicio remoto no responde.")

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        # En semi-abierto, un solo fallo vuelve a abrir el circuito
        self._failures += 1
        if self.state == "half_open" or self._failures >= self.failure_threshold:
            self._opened_at = self._clock()
