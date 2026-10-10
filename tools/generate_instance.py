"""Generador de instancias de TileUp parametrizado por N, K, M y semilla.

    python tools/generate_instance.py N K M --seed S [--max-value V] [-o archivo]

Los colores se eligen uniformemente en 1..K y los valores en 1..V. El valor de las
fichas no afecta la factibilidad (la fusión conserva la suma), solo la ficha mayor.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path


def generate(n: int, k: int, m: int, seed: int, max_value: int = 9) -> str:
    rng = random.Random(seed)
    lines = [
        f"# TileUp -- instancia generada N={n} K={k} M={m} semilla={seed}",
        f"{n} {k}",
        f"{m}",
    ]
    lines += [f"{rng.randint(1, k)} {rng.randint(1, max_value)}" for _ in range(m)]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("n", type=int)
    parser.add_argument("k", type=int)
    parser.add_argument("m", type=int)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-value", type=int, default=9)
    parser.add_argument("-o", "--out", help="archivo de salida (por defecto, salida estándar)")
    args = parser.parse_args()
    if args.n < 1 or args.k < 1 or args.m < 0 or args.max_value < 1:
        parser.error("se requiere N >= 1, K >= 1, M >= 0 y --max-value >= 1")
    text = generate(args.n, args.k, args.m, args.seed, args.max_value)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
