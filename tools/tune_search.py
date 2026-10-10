"""Ajuste de parámetros de la función de evaluación del agente de búsqueda.

    python tools/tune_search.py [--widths 16 64] [--workers 4] [--out results/tuning_busqueda.csv]

Procedimiento:
* Instancias de entrenamiento generadas con semillas 101..103, distintas de las usadas en la
  comparación experimental, en el régimen difícil (K > N^2/2), donde los parámetros importan.
* Cada combinación de la rejilla (beta x lookahead x decay) se evalúa con UNA pasada de beam
  search de ancho fijo, para cada ancho de ``--widths``. Así la medida no depende de la velocidad
  de la máquina y es determinista.
* Criterio: mayor promedio de fichas colocadas sobre todas las instancias y anchos (un ajuste
  robusto al ancho que se alcance con el tiempo disponible); desempate por menor ocupación.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tileup.agents.base import Deadline  # noqa: E402
from tileup.agents.beam_search import BeamSearchAgent, zobrist_table  # noqa: E402
from tileup.instance import parse_instance  # noqa: E402
from tools.generate_instance import generate  # noqa: E402

TRAIN_CONFIGS = [(4, 12, 80), (4, 14, 80), (5, 18, 125), (5, 21, 125), (6, 26, 180), (6, 30, 180)]
TRAIN_SEEDS = [101, 102, 103]
GRID = {
    "beta": [0.0, 0.25, 0.5, 1.0, 2.0, 4.0],
    "lookahead": [2, 4, 8, 16],
    "decay": [0.6, 0.8, 1.0],
}


def run_combo(args):
    params, widths = args
    agent = BeamSearchAgent(**params)
    placed = occupied = 0
    for (n, k, m), seed, width in itertools.product(TRAIN_CONFIGS, TRAIN_SEEDS, widths):
        inst = parse_instance(generate(n, k, m, seed))
        agent._demand = agent.demand_table(inst)
        agent._zobrist = zobrist_table(n, k)
        agent._expanded = agent._generated = 0
        state, _, _ = agent.beam_pass(inst, width, random.Random(1), Deadline(float("inf")))
        placed += state.placed
        occupied += state.occupied
    count = len(TRAIN_CONFIGS) * len(TRAIN_SEEDS) * len(widths)
    return params, placed / count, occupied / count


def main() -> int:
    parser = argparse.ArgumentParser(description="Ajuste por rejilla del agente de búsqueda.")
    parser.add_argument("--widths", type=int, nargs="+", default=[16, 64])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default="results/tuning_busqueda.csv")
    args = parser.parse_args()

    combos = [dict(zip(GRID, values)) for values in itertools.product(*GRID.values())]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(run_combo, [(c, args.widths) for c in combos]))
    rows.sort(key=lambda r: (-r[1], r[2]))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["beta", "lookahead", "decay", "colocadas_prom", "ocupadas_prom"])
        for params, placed, occupied in rows:
            writer.writerow([params["beta"], params["lookahead"], params["decay"], f"{placed:.2f}", f"{occupied:.2f}"])
    print(f"anchos={args.widths}  combinaciones={len(rows)}  resultados en {out}")
    for params, placed, occupied in rows[:10]:
        print(f"  beta={params['beta']:<5} lookahead={params['lookahead']:<3} decay={params['decay']:<4} "
              f"colocadas={placed:7.2f} ocupadas={occupied:6.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
