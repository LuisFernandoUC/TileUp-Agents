"""Comparación de agentes sobre instancias generadas, con varias semillas por agente.

    python tools/compare_agents.py [--agentes busqueda evolutivo aleatorio] [--semillas 1 2 ... 10]
                                   [--semillas-instancia 201 202] [--time-limit 10] [--workers 4]
                                   [--out results/comparacion_agentes.csv]

Cada corrida replica lo que hace ``python -m tileup solve``: el agente recibe el límite menos el margen
del programa, y las métricas salen de repetir sus colocaciones sobre el motor. Las instancias son las
mismas configuraciones (N, K, M) del ajuste, con semillas de instancia distintas (por defecto 201 y 202,
frente a 101..103 del ajuste), para no evaluar sobre lo que sirvió para ajustar parámetros.

Escribe una fila por corrida y imprime una tabla por configuración: media y desviación de las fichas
colocadas, victorias y ocupación media de las partidas ganadas.

Las corridas del agente de búsqueda dependen del reloj, así que con muchos workers en paralelo conviene
dejar núcleos libres: ``--workers`` no debería superar la mitad de los núcleos físicos.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tileup.agents import AGENTS, Deadline  # noqa: E402
from tileup.cli import time_budget  # noqa: E402
from tileup.engine import GameState  # noqa: E402
from tileup.instance import parse_instance  # noqa: E402
from tools.generate_instance import generate  # noqa: E402

CONFIGS = [(4, 12, 80), (4, 14, 80), (5, 18, 125), (5, 21, 125), (6, 26, 180), (6, 30, 180)]


def run_one(args):
    agente, (n, k, m), semilla_inst, semilla, limite = args
    instancia = parse_instance(generate(n, k, m, semilla_inst))
    inicio = time.perf_counter()
    resultado = AGENTS[agente]().solve(instancia, semilla, Deadline(time_budget(limite), start=inicio))
    estado = GameState(instancia)
    for fila, col in resultado.placements:
        if estado.is_terminal:
            break
        estado.place(fila, col)
    return (agente, n, k, m, semilla_inst, semilla, estado.placed, estado.occupied,
            estado.status.value, round(time.perf_counter() - inicio, 3), resultado.effort)


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparación de agentes con varias semillas.")
    parser.add_argument("--agentes", nargs="+", default=["busqueda", "evolutivo", "aleatorio"], choices=sorted(AGENTS))
    parser.add_argument("--semillas", type=int, nargs="+", default=list(range(1, 11)))
    parser.add_argument("--semillas-instancia", type=int, nargs="+", default=[201, 202])
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default="results/comparacion_agentes.csv")
    args = parser.parse_args()

    tareas = [(a, cfg, si, s, args.time_limit)
              for a, cfg, si, s in itertools.product(args.agentes, CONFIGS, args.semillas_instancia, args.semillas)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        filas = list(pool.map(run_one, tareas))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["agente", "n", "k", "m", "semilla_instancia", "semilla", "colocadas", "ocupadas",
                           "resultado", "tiempo", "esfuerzo"])
        escritor.writerows(filas)

    por_grupo = defaultdict(list)
    for f in filas:
        por_grupo[(f[0], (f[1], f[2], f[3]))].append(f)
    print(f"limite={args.time_limit}s  semillas={args.semillas}  semillas de instancia={args.semillas_instancia}")
    for cfg in CONFIGS:
        print(f"\nN={cfg[0]} K={cfg[1]} M={cfg[2]}")
        for agente in args.agentes:
            g = por_grupo[(agente, cfg)]
            col = [f[6] for f in g]
            ganadas = [f for f in g if f[8] == "victoria"]
            ocup = f"{statistics.mean(f[7] for f in ganadas):.1f}" if ganadas else "-"
            print(f"  {agente:<10} colocadas={statistics.mean(col):6.2f} (±{statistics.pstdev(col):5.2f})"
                  f"  victorias={len(ganadas)}/{len(g)}  ocupadas_en_victorias={ocup}"
                  f"  t_medio={statistics.mean(f[9] for f in g):.1f}s")
    print("\nTOTAL")
    for agente in args.agentes:
        g = [f for f in filas if f[0] == agente]
        col = [f[6] for f in g]
        print(f"  {agente:<10} colocadas={statistics.mean(col):6.2f} (±{statistics.pstdev(col):5.2f})"
              f"  victorias={sum(f[8] == 'victoria' for f in g)}/{len(g)}")
    print(f"\nresultados en {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
