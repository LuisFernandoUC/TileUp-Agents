"""Punto de entrada de línea de comandos.

    python -m tileup play <instancia> [--out solucion.txt] [--no-color]

``play`` permite jugar TileUp manualmente en la consola. Los subcomandos de los
agentes se agregarán aquí mismo en una etapa posterior.
"""

from __future__ import annotations

import argparse
import os
import sys

from .engine import GameState, IllegalMoveError, Status
from .instance import InstanceError, load_instance
from .solution import summary_line, write_solution

# Fondos ANSI para distinguir colores; si K supera la paleta, se reciclan.
_PALETTE = ["41", "42", "43", "44", "45", "46", "101", "102", "103", "104", "105", "106"]

HELP = """Comandos:
  <fila> <columna>   coloca la ficha actual (ambas desde 0), p. ej. "1 2"
  h                  muestra esta ayuda
  q                  abandona la partida (se guarda la solución parcial si se usó --out)"""


def _make_color_fn(enabled: bool):
    if not enabled:
        return None
    if os.name == "nt":
        os.system("")  # habilita las secuencias ANSI en la consola de Windows
    return lambda text, color: f"\033[30;{_PALETTE[(color - 1) % len(_PALETTE)]}m{text}\033[0m"


def _preview(state: GameState, count: int = 5) -> str:
    tiles = state.instance.tiles[state.next_index : state.next_index + count]
    return " ".join(f"{t.color}:{t.value}" for t in tiles) or "-"


def play(args: argparse.Namespace) -> int:
    instance = load_instance(args.instance)
    state = GameState(instance)
    color_fn = _make_color_fn(args.color and sys.stdout.isatty())

    print(f"TileUp {instance.n}x{instance.n}, K={instance.k}, M={instance.m}. Fichas como color:valor.")
    print(HELP)
    while not state.is_terminal:
        print()
        print(state.render(color_fn))
        tile = state.next_tile()
        print(
            f"Ficha {state.next_index}/{instance.m - 1}: {tile.color}:{tile.value}   "
            f"siguientes: {_preview(state)}   ocupadas: {state.occupied}/{instance.n ** 2}"
        )
        try:
            line = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line in ("q", "quit", "salir"):
            break
        if line in ("h", "help", "ayuda", ""):
            print(HELP)
            continue
        parts = line.replace(",", " ").split()
        if len(parts) != 2 or not all(p.lstrip("-").isdigit() for p in parts):
            print("Entrada no válida; escriba fila y columna, p. ej. '0 3'.")
            continue
        try:
            result = state.place(int(parts[0]), int(parts[1]))
        except IllegalMoveError as exc:
            print(f"Jugada ilegal: {exc}")
            continue
        if result.group_size > 1:
            print(f"Fusión de {result.group_size} fichas -> valor {result.value}")

    print()
    print(state.render(color_fn))
    outcome = {Status.WON: "VICTORIA", Status.LOST: "DERROTA", Status.IN_PROGRESS: "ABANDONADA"}
    print(f"Partida {outcome[state.status]}. {summary_line(state)[2:]}")
    if args.out:
        write_solution(args.out, state)
        print(f"Solución escrita en {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tileup", description="TileUp: motor del juego y agentes.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_play = sub.add_parser("play", help="jugar manualmente una instancia en la consola")
    p_play.add_argument("instance", help="ruta del archivo de instancia")
    p_play.add_argument("--out", help="archivo donde escribir la solución al terminar")
    p_play.add_argument("--no-color", dest="color", action="store_false", help="desactiva los colores ANSI")
    p_play.set_defaults(func=play)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Salida en UTF-8 aunque se redirija a un archivo o tubería (en Windows sería cp1252).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except InstanceError as exc:
        print(f"error: instancia inválida: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
