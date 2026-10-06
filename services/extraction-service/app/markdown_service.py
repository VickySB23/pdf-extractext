"""Conversión del texto de un PDF a Markdown básico (lógica pura, sin FastAPI).

Heurística: el "cuerpo" es el tamaño de fuente con más caracteres de todo el
documento (contando por tamaño redondeado: 11.0 y 11.4 son el mismo cuerpo).
Las líneas con un tamaño proporcionalmente más grande que el cuerpo son
títulos (#, ##, ###); un renglón corto en negrita sin punto final es
subtítulo (####). Las viñetas pasan a "-". Las líneas de un mismo bloque se
juntan en un párrafo y los bloques se separan con una línea en blanco.
"""
import re

import pymupdf

# Espacios raros que aparecen en PDFs (nbsp, en/em quad, tabuladores, ...).
# Se reemplazan por un espacio común; las corridas se colapsan después.
_ESPACIOS = str.maketrans(
    {
        **{chr(c): " " for c in range(0x2000, 0x200B)},  # en/em/thin quad, etc.
        "\t": " ",
        "\n": " ",
        "\r": " ",
        "\xa0": " ",    # no-break space
        "\u1680": " ",  # ogham space mark
        "\u200b": " ",  # zero-width space
        "\u2028": " ",  # line separator
        "\u2029": " ",  # paragraph separator
        "\u202f": " ",  # narrow no-break space
        "\u205f": " ",  # medium mathematical space
        "\u3000": " ",  # ideographic space
    }
)

# Marcas de lista: las originales (- • ◦ · *) más – ● ▪ ‣.
_MARCAS_DE_VINETA = "-•◦·*\u2013\u25cf\u25aa\u2023"
_NEGRITA = 16  # bit 4 de span["flags"] en PyMuPDF
_LARGO_MAX_SUBTITULO = 60
_PUNTO_FINAL = (".", "!", "?", "…")
_RATIOS = ((1.60, 1), (1.30, 2), (1.12, 3))  # (ratio mínimo con el cuerpo, nivel)


def normalizar_espacios(texto: str) -> str:
    """Espacios raros -> espacio común, corridas colapsadas y bordes recortados."""
    return re.sub(r" {2,}", " ", texto.translate(_ESPACIOS)).strip()


def a_markdown(doc: pymupdf.Document) -> str:
    """Documento PyMuPDF -> Markdown básico. Devuelve "" si no hay texto.

    Una sola pasada de lectura, guardando tuplas compactas (no los dicts de
    PyMuPDF, que ocupan muchísima memoria en documentos largos).
    TEXTFLAGS_TEXT es obligatorio: sin él, get_text("dict") también extrae
    imágenes y el mismo PDF pasa de ~14 ms a ~1.4 s por página.
    """
    lineas: list[tuple[tuple[int, int], str, float, bool]] = []
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
                # Negrita: por flags o por el nombre de la fuente (hay fuentes
                # con "bold" en el nombre que MuPDF no marca como negrita).
                negrita = (
                    bool(dominante["flags"] & _NEGRITA)
                    or "bold" in dominante["font"].lower()
                )
                lineas.append(((pno, bno), texto, dominante["size"], negrita))

    if not lineas:
        return ""

    # Cuerpo = tamaño de fuente con más caracteres. Se cuenta por round(tam):
    # los PDFs derivan tamaños fraccionarios (11.0 y 11.4 son el mismo cuerpo).
    conteo: dict[int, int] = {}
    for _, texto, tam, _ in lineas:
        redondo = round(tam)
        conteo[redondo] = conteo.get(redondo, 0) + len(texto)
    cuerpo = max(conteo, key=lambda tam: conteo[tam])

    salida: list[str] = []
    parrafo: list[str] = []
    clave_de_bloque: tuple[int, int] | None = None
    nivel_anterior: int | None = None

    def volcar_parrafo() -> None:
        if parrafo:
            salida.append(" ".join(parrafo))
            parrafo.clear()

    for clave, texto, tam, negrita in lineas:
        # a) viñeta: la marca manda sobre el tamaño de la letra
        if texto[0] in _MARCAS_DE_VINETA and len(texto) > 1 and texto[1] == " ":
            volcar_parrafo()
            nivel_anterior = None
            salida.append("- " + texto[1:].lstrip())
            continue

        # b) título por proporción de tamaño (el ratio usa el tamaño real de la
        #    línea, no el redondeado). Un renglón de UN carácter (letra
        #    capitular como "P") NUNCA es título: se degrada a párrafo y el
        #    carácter se conserva.
        nivel = 0
        if len(texto) > 1:
            ratio = tam / cuerpo
            for minimo, n in _RATIOS:
                if ratio >= minimo:
                    nivel = n
                    break
            if nivel == 0 and negrita and len(texto) < _LARGO_MAX_SUBTITULO:
                if not texto.endswith(_PUNTO_FINAL):
                    nivel = 4

        if nivel:
            volcar_parrafo()
            if nivel_anterior == nivel and salida:
                # títulos consecutivos del mismo nivel: un solo renglón
                salida[-1] = f"{salida[-1]} {texto}"
            else:
                salida.append(f"{'#' * nivel} {texto}")
            nivel_anterior = nivel
            continue

        # c) párrafo: las líneas del mismo bloque van juntas
        if clave != clave_de_bloque:
            volcar_parrafo()
            clave_de_bloque = clave
        parrafo.append(texto)
        nivel_anterior = None  # una línea de cuerpo corta la racha de títulos

    volcar_parrafo()  # lo que quedó pendiente en la última página
    return "\n\n".join(salida)
