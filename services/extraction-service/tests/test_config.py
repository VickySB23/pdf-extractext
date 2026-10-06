"""Arranque: lectura, validación y anuncio de la configuración por stdout."""
import importlib

import pytest

from app import main

VARIABLES = (
    "MAX_CONCURRENT",
    "QUEUE_TIMEOUT_SECONDS",
    "RETRY_AFTER_SECONDS",
    "MAX_UPLOAD_SIZE_BYTES",
    "OUTPUT_FORMAT",
)
INVALIDAS = ["cero", "0", "-1", "1.5", "", "  ", "10 MB"]
INVALIDAS_ELECCION = ["html", "texto", "Markdown, text", "", "  "]


@pytest.fixture
def restaurar_main(monkeypatch):
    """Deja app.main como estaba: los reloads los ejecutan en el sitio."""
    yield
    for nombre in VARIABLES:
        monkeypatch.delenv(nombre, raising=False)
    importlib.reload(main)


@pytest.mark.parametrize("valor", INVALIDAS)
def test_read_positive_int_rechaza_valores_invalidos(monkeypatch, valor):
    monkeypatch.setenv("MAX_CONCURRENT", valor)
    with pytest.raises(RuntimeError, match="MAX_CONCURRENT"):
        main._read_positive_int("MAX_CONCURRENT", 1)


@pytest.mark.parametrize(
    "nombre,default",
    [
        ("MAX_CONCURRENT", 1),
        ("QUEUE_TIMEOUT_SECONDS", 20),
        ("RETRY_AFTER_SECONDS", 1),
        ("MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024),
    ],
)
def test_read_positive_int_usa_el_default_si_no_esta_definida(monkeypatch, nombre, default):
    monkeypatch.delenv(nombre, raising=False)
    assert main._read_positive_int(nombre, default) == default


def test_max_concurrent_invalido_falla_al_arrancar(monkeypatch, restaurar_main):
    """Un valor inválido detiene el arranque en vez de aceptarse en silencio."""
    monkeypatch.setenv("MAX_CONCURRENT", "muchos")
    with pytest.raises(RuntimeError, match="MAX_CONCURRENT"):
        importlib.reload(main)


@pytest.mark.parametrize("valor", INVALIDAS_ELECCION)
def test_read_choice_rechaza_valores_invalidos(monkeypatch, valor):
    monkeypatch.setenv("OUTPUT_FORMAT", valor)
    with pytest.raises(RuntimeError, match="OUTPUT_FORMAT"):
        main._read_choice("OUTPUT_FORMAT", "markdown", ("markdown", "text"))


def test_read_choice_usa_el_default_si_no_esta_definida(monkeypatch):
    monkeypatch.delenv("OUTPUT_FORMAT", raising=False)
    assert main._read_choice("OUTPUT_FORMAT", "markdown", ("markdown", "text")) == "markdown"


def test_read_choice_ignora_mayusculas_y_espacios(monkeypatch):
    monkeypatch.setenv("OUTPUT_FORMAT", "  TEXT ")
    assert main._read_choice("OUTPUT_FORMAT", "markdown", ("markdown", "text")) == "text"


def test_output_format_invalido_falla_al_arrancar(monkeypatch, restaurar_main):
    """Un OUTPUT_FORMAT inválido detiene el arranque, igual que las otras vars."""
    monkeypatch.setenv("OUTPUT_FORMAT", "html")
    with pytest.raises(RuntimeError, match="OUTPUT_FORMAT"):
        importlib.reload(main)


def test_el_arranque_anuncia_la_configuracion_por_stdout(monkeypatch, restaurar_main, capsys):
    monkeypatch.setenv("MAX_CONCURRENT", "7")
    monkeypatch.setenv("OUTPUT_FORMAT", "text")
    importlib.reload(main)
    salida = capsys.readouterr().out
    assert "MAX_CONCURRENT=7" in salida
    assert "QUEUE_TIMEOUT_SECONDS=20" in salida
    assert "OUTPUT_FORMAT=text" in salida