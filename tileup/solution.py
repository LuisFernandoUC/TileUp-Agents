"""Escritura del archivo de solución.

Una línea ``indice fila columna`` por colocación (todo desde cero) y una línea final
``# colocadas=X ocupadas=Y mayor=Z``. Se escribe aunque la partida termine en derrota.
"""

from __future__ import annotations

from pathlib import Path

from .engine import GameState


def summary_line(state: GameState) -> str:
    return f"# colocadas={state.placed} ocupadas={state.occupied} mayor={state.max_value}"


def format_solution(state: GameState) -> str:
    lines = [f"{i} {r} {c}" for i, (r, c) in enumerate(state.placements)]
    lines.append(summary_line(state))
    return "\n".join(lines) + "\n"


def write_solution(path: str | Path, state: GameState) -> None:
    path = Path(path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_solution(state), encoding="utf-8")
