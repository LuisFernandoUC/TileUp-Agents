"""Punto de entrada de línea de comandos.

    python -m tileup solve <instancia> --agent NOMBRE --seed S --time-limit T [--out solucion.txt]
    python -m tileup play  <instancia> [--out solucion.txt] [--no-color]

``solve`` es el punto de entrada oficial: ejecuta un agente sobre la instancia, escribe el
archivo de solución e informa las métricas por salida estándar. ``play`` permite jugar
TileUp manualmente en la consola.

Códigos de salida: 0 éxito (aunque la partida termine en derrota), 1 error de E/S,
2 instancia inválida o argumentos incorrectos, 3 el agente propuso una jugada ilegal.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .agents import AGENTS, Deadline
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


def time_budget(limit: float) -> float:
    """Tiempo que se le concede al agente: el límite menos un margen para escribir la solución."""
    margin = min(1.0, max(0.05, 0.1 * limit))
    return max(0.0, limit - margin)


def solve(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    if args.time_limit <= 0:
        print("error: --time-limit debe ser positivo", file=sys.stderr)
        return 2
    instance = load_instance(args.instance)
    agent = AGENTS[args.agent]()
    deadline = Deadline(time_budget(args.time_limit), start=start)
    result = agent.solve(instance, args.seed, deadline)

    # Las colocaciones se aplican sobre un estado nuevo del motor: el agente no puede
    # saltarse las reglas, y las métricas informadas salen del motor, no del agente.
    state = GameState(instance)
    for step, (row, col) in enumerate(result.placements):
        if state.is_terminal:
            break
        try:
            state.place(row, col)
        except IllegalMoveError as exc:
            print(f"error: el agente '{args.agent}' propuso una jugada ilegal en el paso {step}: {exc}", file=sys.stderr)
            return 3

    out = args.out or Path("solutions") / f"{Path(args.instance).stem}.{args.agent}.s{args.seed}.txt"
    write_solution(out, state)
    elapsed = time.perf_counter() - start

    print(f"agente={args.agent} semilla={args.seed} limite={args.time_limit}s instancia={args.instance}")
    print(f"colocadas={state.placed} ocupadas={state.occupied} mayor={state.max_value} resultado={state.status.value}")
    print(f"tiempo={elapsed:.3f}s {agent.effort_name}={result.effort}")
    for key, value in result.stats.items():
        print(f"{key}={value}")
    print(f"solucion={out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tileup", description="TileUp: motor del juego y agentes.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_solve = sub.add_parser("solve", help="resolver una instancia con un agente")
    p_solve.add_argument("instance", help="ruta del archivo de instancia")
    p_solve.add_argument("--agent", required=True, choices=sorted(AGENTS), help="agente a utilizar")
    p_solve.add_argument("--seed", type=int, required=True, help="semilla; fija todo el azar del agente")
    p_solve.add_argument("--time-limit", type=float, required=True, help="límite de tiempo en segundos")
    p_solve.add_argument("--out", help="archivo de solución (por defecto solutions/<instancia>.<agente>.s<semilla>.txt)")
    p_solve.set_defaults(func=solve)

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
