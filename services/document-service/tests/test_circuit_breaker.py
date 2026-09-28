import pytest

from app.infrastructure.clients.circuit_breaker import CircuitBreaker, CircuitOpenError


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_se_abre_tras_n_fallos_y_se_recupera():
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=2, reset_timeout=10, clock=clock)
    assert cb.state == "closed"

    cb.record_failure()
    assert cb.state == "closed"
    cb.record_failure()
    assert cb.state == "open"
    with pytest.raises(CircuitOpenError):
        cb.before_call()

    clock.now = 10
    assert cb.state == "half_open"
    cb.before_call()  # deja pasar una llamada de prueba
    cb.record_success()
    assert cb.state == "closed"


def test_un_fallo_en_semi_abierto_vuelve_a_abrir():
    clock = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=5, clock=clock)
    cb.record_failure()
    clock.now = 5
    assert cb.state == "half_open"
    cb.record_failure()
    assert cb.state == "open"
