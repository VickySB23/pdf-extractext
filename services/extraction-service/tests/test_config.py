"""Arranque: lectura, validación y anuncio de la configuración en el log."""
import importlib
import logging

import pytest

from app.core import config
from app.domain.extraction import FORMATOS, FORMATO_POR_DEFECTO

VARIABLES = (
    "QUEUE_TIMEOUT_SECONDS",
    "RETRY_AFTER_SECONDS",
    "MAX_UPLOAD_SIZE_BYTES",
    "OUTPUT_FORMAT",
    "RATE_LIMIT_AVERAGE",
    "RATE_LIMIT_BURST",
)
INVALIDAS = ["cero", "0", "-1", "1.5", "", "  ", "10 MB"]
INVALIDAS_ELECCION = ["html", "texto", "Markdown, text", "", "  "]


@pytest.fixture
def restaurar_config(monkeypatch):
    """Deja la configuración como estaba: los reloads los ejecutan en el sitio."""
    yield
    for nombre in VARIABLES:
        monkeypatch.delenv(nombre, raising=False)
    importlib.reload(config)


@pytest.mark.parametrize("valor", INVALIDAS)
def test_read_positive_int_rechaza_valores_invalidos(monkeypatch, valor):
    monkeypatch.setenv("QUEUE_TIMEOUT_SECONDS", valor)
    with pytest.raises(RuntimeError, match="QUEUE_TIMEOUT_SECONDS"):
        config._read_positive_int("QUEUE_TIMEOUT_SECONDS", 1)


@pytest.mark.parametrize(
    "nombre,default",
    [
        ("QUEUE_TIMEOUT_SECONDS", 20),
        ("RETRY_AFTER_SECONDS", 1),
        ("MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024),
    ],
)
def test_read_positive_int_usa_el_default_si_no_esta_definida(monkeypatch, nombre, default):
    monkeypatch.delenv(nombre, raising=False)
    assert config._read_positive_int(nombre, default) == default


def test_el_rate_limit_tiene_valores_por_defecto(monkeypatch, restaurar_config):
    monkeypatch.delenv("RATE_LIMIT_AVERAGE", raising=False)
    monkeypatch.delenv("RATE_LIMIT_BURST", raising=False)
    importlib.reload(config)
    assert (config.RATE_LIMIT_AVERAGE, config.RATE_LIMIT_BURST) == (20, 40)


def test_queue_timeout_invalido_falla_al_arrancar(monkeypatch, restaurar_config):
    """Un valor inválido detiene el arranque en vez de aceptarse en silencio."""
    monkeypatch.setenv("QUEUE_TIMEOUT_SECONDS", "muchos")
    with pytest.raises(RuntimeError, match="QUEUE_TIMEOUT_SECONDS"):
        importlib.reload(config)


@pytest.mark.parametrize("valor", INVALIDAS_ELECCION)
def test_read_choice_rechaza_valores_invalidos(monkeypatch, valor):
    monkeypatch.setenv("OUTPUT_FORMAT", valor)
    with pytest.raises(RuntimeError, match="OUTPUT_FORMAT"):
        config._read_choice("OUTPUT_FORMAT", FORMATO_POR_DEFECTO, FORMATOS)


def test_read_choice_usa_el_default_si_no_esta_definida(monkeypatch):
    monkeypatch.delenv("OUTPUT_FORMAT", raising=False)
    assert config._read_choice("OUTPUT_FORMAT", FORMATO_POR_DEFECTO, FORMATOS) == "markdown"


def test_read_choice_ignora_mayusculas_y_espacios(monkeypatch):
    monkeypatch.setenv("OUTPUT_FORMAT", "  TEXT ")
    assert config._read_choice("OUTPUT_FORMAT", FORMATO_POR_DEFECTO, FORMATOS) == "text"


def test_output_format_invalido_falla_al_arrancar(monkeypatch, restaurar_config):
    """Un OUTPUT_FORMAT inválido detiene el arranque, igual que las otras vars."""
    monkeypatch.setenv("OUTPUT_FORMAT", "html")
    with pytest.raises(RuntimeError, match="OUTPUT_FORMAT"):
        importlib.reload(config)


def test_el_arranque_anuncia_la_configuracion_en_el_log(monkeypatch, restaurar_config, caplog):
    monkeypatch.setenv("QUEUE_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("OUTPUT_FORMAT", "text")
    with caplog.at_level(logging.INFO, logger="extraction-service"):
        importlib.reload(config)
    assert "QUEUE_TIMEOUT_SECONDS=7" in caplog.text
    assert "OUTPUT_FORMAT=text" in caplog.text
