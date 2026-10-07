"""Conversión a Markdown básico basada en tamaños de fuente, negrita y viñetas.
El cuerpo del documento se infiere por el tamaño con más caracteres.
"""
import re
from typing import NamedTuple

import pymupdf

_MARCAS_DE_VINETA = "-•◦·*–●▪‣"
_NEGRITA = 16
_LARGO_MAX_SUBTITULO = 60
_PUNTO_FINAL = (".", "!", "?", "…")
_RATIOS = ((1.60, 1), (1.30, 2), (1.12, 3))


class Linea(NamedTuple):
    clave: tuple[int, int]
    texto: str
    tamano: float
    negrita: bool


def normalizar_espacios(texto: str) -> str:
    return re.sub(r"[\s\u200b]+", " ", texto).strip()


def _leer_lineas(doc: pymupdf.Document) -> list[Linea]:
    lineas: list[Linea] = []
    for pno, pagina in enumerate(doc):
        # get_text("dict") exige TEXTFLAGS_TEXT: sin eso, 1,4 s vs 14 ms por página.
        datos = pagina.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)
        for bno, bloque in enumerate(datos["blocks"]):
            if bloque["type"] != 0:
                continue
            for linea in bloque["lines"]:
                texto = normalizar_espacios("".join(s["text"] for s in linea["spans"]))
                if not texto:
                    continue
                dominante = max(linea["spans"], key=lambda s: len(s["text"]))
                negrita = bool(dominante["flags"] & _NEGRITA)
                lineas.append(Linea((pno, bno), texto, dominante["size"], negrita))
    return lineas


def _tamano_cuerpo(lineas: list[Linea]) -> int:
    conteo: dict[int, int] = {}
    for linea in lineas:
        redondo = round(linea.tamano)
        conteo[redondo] = conteo.get(redondo, 0) + len(linea.texto)
    return max(conteo, key=lambda tam: conteo[tam])


def _nivel_titulo(linea: Linea, cuerpo: int) -> int:
    if len(linea.texto) <= 1:
        return 0
    ratio = linea.tamano / cuerpo
    for minimo, n in _RATIOS:
        if ratio >= minimo:
            return n
    if (
        linea.negrita
        and len(linea.texto) < _LARGO_MAX_SUBTITULO
        and not linea.texto.endswith(_PUNTO_FINAL)
    ):
        return 4
    return 0


def a_markdown(doc: pymupdf.Document) -> str:
    lineas = _leer_lineas(doc)
    if not lineas:
        return ""
    cuerpo = _tamano_cuerpo(lineas)

    salida: list[str] = []
    parrafo: list[str] = []
    clave_de_bloque: tuple[int, int] | None = None
    nivel_anterior: int | None = None

    def volcar_parrafo() -> None:
        if parrafo:
            salida.append(" ".join(parrafo))
            parrafo.clear()

    for linea in lineas:
        if linea.texto[0] in _MARCAS_DE_VINETA and len(linea.texto) > 1 and linea.texto[1] == " ":
            volcar_parrafo()
            nivel_anterior = None
            salida.append("- " + linea.texto[1:].lstrip())
            continue

        nivel = _nivel_titulo(linea, cuerpo)
        if nivel:
            volcar_parrafo()
            if nivel_anterior == nivel and salida:
                salida[-1] = f"{salida[-1]} {linea.texto}"
            else:
                salida.append(f"{'#' * nivel} {linea.texto}")
            nivel_anterior = nivel
            continue

        if linea.clave != clave_de_bloque:
            volcar_parrafo()
            clave_de_bloque = linea.clave
        parrafo.append(linea.texto)
        nivel_anterior = None

    volcar_parrafo()
    return "\n\n".join(salida)
