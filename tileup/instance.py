"""Lectura de instancias en el formato de la especificación.

Formato: líneas en blanco y comentarios (desde ``#`` hasta el fin de línea) se ignoran.
Luego, en orden: una línea ``N K``, una línea ``M`` y M líneas ``color valor``.

Cualquier desviación produce ``InstanceError`` con un mensaje legible que indica la
línea del archivo; nunca una excepción sin controlar.
"""

from __future__ import annotations

from pathlib import Path

from .engine import Instance, Tile


class InstanceError(ValueError):
    """La instancia está mal formada o no se puede leer."""


def _ints(lineno: int, tokens: list[str], expected: int, what: str) -> list[int]:
    if len(tokens) != expected:
        raise InstanceError(
            f"línea {lineno}: se esperaban {expected} entero(s) ({what}), "
            f"se encontraron {len(tokens)}: {' '.join(tokens)!r}"
        )
    try:
        return [int(t) for t in tokens]
    except ValueError:
        raise InstanceError(f"línea {lineno}: valor no entero en {what}: {' '.join(tokens)!r}") from None


def parse_instance(text: str) -> Instance:
    rows: list[tuple[int, list[str]]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if line:
            rows.append((lineno, line.split()))

    if not rows:
        raise InstanceError("la instancia está vacía: falta la línea 'N K'")

    lineno, tokens = rows[0]
    n, k = _ints(lineno, tokens, 2, "N K")
    if n < 1:
        raise InstanceError(f"línea {lineno}: N debe ser >= 1 (se leyó {n})")
    if k < 1:
        raise InstanceError(f"línea {lineno}: K debe ser >= 1 (se leyó {k})")

    if len(rows) < 2:
        raise InstanceError("falta la línea con M (cantidad de fichas)")
    lineno, tokens = rows[1]
    (m,) = _ints(lineno, tokens, 1, "M")
    if m < 0:
        raise InstanceError(f"línea {lineno}: M debe ser >= 0 (se leyó {m})")

    tile_rows = rows[2:]
    if len(tile_rows) < m:
        raise InstanceError(f"se esperaban {m} fichas y solo hay {len(tile_rows)}")
    if len(tile_rows) > m:
        extra_line = tile_rows[m][0]
        raise InstanceError(f"línea {extra_line}: contenido extra; la instancia declara M={m} fichas")

    tiles = []
    for i, (lineno, tokens) in enumerate(tile_rows):
        color, value = _ints(lineno, tokens, 2, f"color valor de la ficha {i}")
        if not 1 <= color <= k:
            raise InstanceError(f"línea {lineno}: color {color} fuera del rango 1..{k}")
        if value < 1:
            raise InstanceError(f"línea {lineno}: el valor debe ser positivo (se leyó {value})")
        tiles.append(Tile(color, value))

    return Instance(n=n, k=k, tiles=tuple(tiles))


def load_instance(path: str | Path) -> Instance:
    try:
        # utf-8-sig tolera el BOM que agregan algunos editores en Windows.
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise InstanceError(f"no existe el archivo de instancia: {path}") from None
    except UnicodeDecodeError:
        raise InstanceError(f"el archivo {path} no es texto UTF-8 válido") from None
    except OSError as exc:
        raise InstanceError(f"no se pudo leer {path}: {exc.strerror or exc}") from None
    return parse_instance(text)
