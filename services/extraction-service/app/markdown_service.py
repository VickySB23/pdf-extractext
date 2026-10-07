"""Conversión del texto de un PDF a Markdown básico (lógica pura, sin FastAPI).

Heurística: el "cuerpo" es el tamaño de fuente con más caracteres de todo el
documento (contando por tamaño redondeado: 11.0 y 11.4 son el mismo cuerpo).
Las líneas con un tamaño proporcionalmente más grande que el cuerpo son
títulos (#, ##, ###); un renglón corto en negrita sin punto final es
subtítulo (####). Las viñetas pasan a "-". Las líneas de un mismo bloque se
juntan en un párrafo y los bloques se separan con una línea en blanco.
"""
import re
from typing import NamedTuple

import pymupdf

# Marcas de lista aceptadas como viñeta.
_MARCAS_DE_VINETA = "-•◦·*–●▪‣"
_NEGRITA = 16  # bit 4 de span["flags"] en PyMuPDF
_LARGO_MAX_SUBTITULO = 60
_PUNTO_FINAL = (".", "!", "?", "…")
_RATIOS = ((1.60, 1), (1.30, 2), (1.12, 3))  # (ratio mínimo con el cuerpo, nivel)


class Linea(NamedTuple):
    clave: tuple[int, int]  # (página, bloque): agrupa las líneas de un párrafo
    texto: str
    tamano: float
    negrita: bool


def normalizar_espacios(texto: str) -> str:
    """Espacios raros -> espacio común, corridas colapsadas y bordes recortados."""
    return re.sub(r"[\s\u200b]+", " ", texto).strip()


def _leer_lineas(doc: pymupdf.Document) -> list[Linea]:
    """Todas las líneas del documento en una sola pasada de lectura.

    Guarda NamedTuples compactos (no los dicts de PyMuPDF, que ocupan
    muchísima memoria en documentos largos). TEXTFLAGS_TEXT es obligatorio:
    sin él, get_text("dict") también extrae imágenes y el mismo PDF pasa de
    ~14 ms a ~1.4 s por página.
    """
    lineas: list[Linea] = []
    for pno, pagina in enumerate(doc):
        datos = pagina.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)
        for bno, bloque in enumerate(datos["blocks"]):
            if bloque["type"] != 0:  # imágenes: no generan texto
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
    """Tamaño de fuente con más caracteres (el "cuerpo" del documento).

    Se cuenta por round(tam): los PDFs derivan tamaños fraccionarios
    (11.0 y 11.4 son el mismo cuerpo).
    """
    conteo: dict[int, int] = {}
    for linea in lineas:
        redondo = round(linea.tamano)
        conteo[redondo] = conteo.get(redondo, 0) + len(linea.texto)
    return max(conteo, key=lambda tam: conteo[tam])


def _nivel_titulo(linea: Linea, cuerpo: int) -> int:
    """0 = párrafo; 1-3 = título por proporción de tamaño; 4 = subtítulo.

    El ratio usa el tamaño real de la línea, no el redondeado. Un renglón de
    UN carácter (letra capitular como "P") NUNCA es título: se degrada a
    párrafo y el carácter se conserva.
    """
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
    """Documento PyMuPDF -> Markdown básico. Devuelve "" si no hay texto."""
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
        # La marca de viñeta manda sobre el tamaño de la letra
        if linea.texto[0] in _MARCAS_DE_VINETA and len(linea.texto) > 1 and linea.texto[1] == " ":
            volcar_parrafo()
            nivel_anterior = None
            salida.append("- " + linea.texto[1:].lstrip())
            continue

        nivel = _nivel_titulo(linea, cuerpo)
        if nivel:
            volcar_parrafo()
            if nivel_anterior == nivel and salida:
                # títulos consecutivos del mismo nivel: un solo renglón
                salida[-1] = f"{salida[-1]} {linea.texto}"
            else:
                salida.append(f"{'#' * nivel} {linea.texto}")
            nivel_anterior = nivel
            continue

        # Párrafo: las líneas del mismo bloque van juntas
        if linea.clave != clave_de_bloque:
            volcar_parrafo()
            clave_de_bloque = linea.clave
        parrafo.append(linea.texto)
        nivel_anterior = None  # una línea de cuerpo corta la racha de títulos

    volcar_parrafo()  # lo que quedó pendiente en la última página
    return "\n\n".join(salida)
