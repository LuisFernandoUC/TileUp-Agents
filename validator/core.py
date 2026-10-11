"""Validador independiente de soluciones TileUp.

Este módulo NO importa nada del paquete ``tileup`` (ni del motor ni de los agentes):
vuelve a implementar desde cero la lectura de la instancia y las reglas del juego, para
que un error en el motor no pueda "contagiarse" al árbitro. Reproduce la partida paso a
paso y rechaza la solución ante la primera irregularidad.

Reglas que verifica:
* cada línea de jugada tiene tres enteros ``indice fila columna``;
* los índices son 0, 1, 2, ... en orden y no superan M - 1;
* la celda está dentro del tablero y vacía en ese momento;
* no hay jugadas después de que la partida terminó (victoria o derrota);
* la última línea es ``# colocadas=X ocupadas=Y mayor=Z`` y coincide con la partida reproducida.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path


class ValidationInputError(Exception):
    """No se pudo leer la instancia o el archivo de solución (problema de entrada)."""


@dataclass
class Report:
    valid: bool
    placed: int = 0
    occupied: int = 0
    largest: int = 0
    outcome: str = "incompleta"  # victoria | derrota | incompleta
    errors: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- lectura de la instancia


def _data_lines(text: str):
    for lineno, raw in enumerate(text.splitlines(), start=1):
        content = raw.split("#", 1)[0].strip()
        if content:
            yield lineno, content.split()


def _to_ints(lineno: int, tokens: list[str], count: int, label: str) -> list[int]:
    if len(tokens) != count:
        raise ValidationInputError(f"instancia, línea {lineno}: se esperaban {count} enteros ({label})")
    try:
        return [int(t) for t in tokens]
    except ValueError:
        raise ValidationInputError(f"instancia, línea {lineno}: {label} no es entero") from None


def read_instance(text: str) -> tuple[int, int, list[tuple[int, int]]]:
    """Devuelve (N, K, secuencia de (color, valor))."""
    lines = list(_data_lines(text))
    if len(lines) < 2:
        raise ValidationInputError("instancia incompleta: faltan las líneas 'N K' y/o 'M'")
    n, k = _to_ints(*lines[0], 2, "N K")
    (m,) = _to_ints(*lines[1], 1, "M")
    if n < 1 or k < 1 or m < 0:
        raise ValidationInputError("instancia: se requiere N >= 1, K >= 1 y M >= 0")
    body = lines[2:]
    if len(body) != m:
        raise ValidationInputError(f"instancia: declara M={m} fichas pero contiene {len(body)}")
    seq = []
    for lineno, tokens in body:
        color, value = _to_ints(lineno, tokens, 2, "color valor")
        if not (1 <= color <= k and value >= 1):
            raise ValidationInputError(f"instancia, línea {lineno}: ficha fuera de rango ({color}, {value})")
        seq.append((color, value))
    return n, k, seq


# ---------------------------------------------------------------- lectura de la solución


def read_solution(text: str) -> tuple[list[tuple[int, list[str]]], tuple[int, str] | None]:
    """Separa las líneas de jugada de la línea resumen final. No interpreta los números."""
    numbered = [(i, line.strip()) for i, line in enumerate(text.splitlines(), start=1) if line.strip()]
    summary = None
    if numbered and numbered[-1][1].startswith("#"):
        summary = numbered.pop()
    moves = [(i, line.split()) for i, line in numbered]
    return moves, summary


def parse_summary(line: str) -> dict[str, int]:
    fields = {}
    for token in line.lstrip("#").split():
        key, sep, value = token.partition("=")
        if sep:
            try:
                fields[key] = int(value)
            except ValueError:
                pass
    return fields


# ---------------------------------------------------------------- reproducción


def _render(grid: list[list[tuple[int, int] | None]]) -> str:
    return "\n".join(
        "  ".join("." if cell is None else f"{cell[0]}:{cell[1]}" for cell in row) for row in grid
    )


def replay(n: int, seq: list[tuple[int, int]], moves, summary, trace: bool = False) -> Report:
    grid: list[list[tuple[int, int] | None]] = [[None] * n for _ in range(n)]
    filled = 0
    placed = 0
    report = Report(valid=True)

    def fail(msg: str) -> Report:
        report.valid = False
        report.errors.append(msg)
        return report

    def finished() -> str | None:
        if placed == len(seq):
            return "victoria"
        if filled == n * n:
            return "derrota"
        return None

    for lineno, tokens in moves:
        report.placed, report.occupied = placed, filled
        if tokens[0].startswith("#"):
            return fail(f"solución, línea {lineno}: solo la última línea puede ser el resumen '#'")
        if len(tokens) != 3:
            return fail(f"solución, línea {lineno}: se esperaban 3 enteros 'indice fila columna'")
        try:
            idx, r, c = (int(t) for t in tokens)
        except ValueError:
            return fail(f"solución, línea {lineno}: valores no enteros {' '.join(tokens)!r}")
        state = finished()
        if state is not None:
            return fail(f"solución, línea {lineno}: jugada después de terminar la partida ({state})")
        if idx != placed:
            return fail(f"solución, línea {lineno}: índice {idx}, se esperaba {placed}")
        if not (0 <= r < n and 0 <= c < n):
            return fail(f"solución, línea {lineno}: celda ({r}, {c}) fuera del tablero {n}x{n}")
        if grid[r][c] is not None:
            return fail(f"solución, línea {lineno}: celda ({r}, {c}) ya ocupada")

        color, value = seq[idx]
        grid[r][c] = (color, value)
        filled += 1
        # Componente conexa del color colocado, por anchura (BFS) sobre la matriz.
        component = [(r, c)]
        visited = {(r, c)}
        queue = deque([(r, c)])
        while queue:
            y, x = queue.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < n and 0 <= nx < n and (ny, nx) not in visited:
                    cell = grid[ny][nx]
                    if cell is not None and cell[0] == color:
                        visited.add((ny, nx))
                        component.append((ny, nx))
                        queue.append((ny, nx))
        if len(component) > 1:
            total = sum(grid[y][x][1] for y, x in component)
            for y, x in component:
                grid[y][x] = None
            grid[r][c] = (color, total)
            filled -= len(component) - 1
        placed += 1
        if trace:
            note = f"fusión de {len(component)}" if len(component) > 1 else "sin fusión"
            report.trace.append(f"paso {idx}: ficha {color}:{value} en ({r},{c}), {note}\n{_render(grid)}")

    report.placed = placed
    report.occupied = filled
    report.largest = max((cell[1] for row in grid for cell in row if cell is not None), default=0)
    report.outcome = finished() or "incompleta"

    if summary is None:
        return fail("solución: falta la línea final '# colocadas=X ocupadas=Y mayor=Z'")
    lineno, line = summary
    declared = parse_summary(line)
    expected = {"colocadas": report.placed, "ocupadas": report.occupied, "mayor": report.largest}
    for key, real in expected.items():
        if key not in declared:
            fail(f"solución, línea {lineno}: el resumen no incluye '{key}='")
        elif declared[key] != real:
            fail(f"solución, línea {lineno}: el resumen declara {key}={declared[key]} pero la partida da {real}")
    return report


def validate_text(instance_text: str, solution_text: str, trace: bool = False) -> Report:
    n, _k, seq = read_instance(instance_text)
    moves, summary = read_solution(solution_text)
    return replay(n, seq, moves, summary, trace)


def validate_files(instance_path: str | Path, solution_path: str | Path, trace: bool = False) -> Report:
    texts = []
    for label, path in (("instancia", instance_path), ("solución", solution_path)):
        try:
            texts.append(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError) as exc:
            raise ValidationInputError(f"no se pudo leer el archivo de {label} {path}: {exc}") from None
    return validate_text(*texts, trace=trace)
