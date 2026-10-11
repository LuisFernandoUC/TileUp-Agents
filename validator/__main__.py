"""python -m validator <instancia> <solucion> [--paso-a-paso]

Código de salida: 0 si la solución es legal, 1 si se rechaza, 2 si no se pudieron leer los archivos.
"""

import argparse
import sys

from .core import ValidationInputError, validate_files


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="validator", description="Validador independiente de soluciones TileUp.")
    parser.add_argument("instance", help="archivo de instancia")
    parser.add_argument("solution", help="archivo de solución")
    parser.add_argument("--paso-a-paso", dest="trace", action="store_true", help="muestra el tablero tras cada jugada")
    args = parser.parse_args()
    try:
        report = validate_files(args.instance, args.solution, trace=args.trace)
    except ValidationInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for step in report.trace:
        print(step, end="\n\n")
    print("VALIDA" if report.valid else "INVALIDA")
    for err in report.errors:
        print(f"  - {err}")
    print(f"colocadas={report.placed} ocupadas={report.occupied} mayor={report.largest} resultado={report.outcome}")
    return 0 if report.valid else 1


sys.exit(main())
