"""Barrido grueso, un parámetro a la vez, del agente evolutivo.

    python tools/tune_evolutivo.py [--tope 100000] [--solo k poblacion] [--semillas 1 2 3] [--workers 4]
                                   [--out results/tuning_evolutivo.csv]

Procedimiento (etapa 1 de docs/decisiones_evolutivo.md, sección 8):
* Mismas instancias de entrenamiento que tune_search.py (semillas 101..103, régimen difícil).
* Partimos de BASE y variamos UN parámetro por vez; los demás quedan en BASE.
* Mismo tope de evaluaciones en todas las configuraciones y sin estancamiento
  (paciencia_fraccion=1.0) ni reloj: el resultado depende solo de las evaluaciones, no de la máquina.
* Cada configuración se corre con varias semillas del algoritmo. Se reporta la media y la
  desviación entre corridas de fichas colocadas y de ocupación final.
* Criterio: mayor promedio de fichas colocadas; desempate por menor ocupación.
* pm se expresa como factor de 1/M (pm = factor / M) para que signifique lo mismo en todas las
  instancias: factor 1.0 = "en promedio un gen mutado por individuo".
"""

from __future__ import annotations

import argparse
import csv
import itertools
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tileup.agents.base import Deadline  # noqa: E402
from tileup.agents.evolutivo import AgenteEvolutivo  # noqa: E402
from tileup.engine import GameState  # noqa: E402
from tileup.instance import parse_instance  # noqa: E402
from tools.generate_instance import generate  # noqa: E402

TRAIN_CONFIGS = [(4, 12, 80), (4, 14, 80), (5, 18, 125), (5, 21, 125), (6, 26, 180), (6, 30, 180)]
TRAIN_SEEDS = [101, 102, 103]

# Punto de partida: en cada barrido se varía un parámetro y los demás quedan aquí.
BASE = {"poblacion": 200, "pm_factor": 2.0, "pc": 0.9, "k": 3, "elites": 2}
SWEEP = {
    "pm_factor": [1.0, 1.5, 2.0, 3.0],
    "poblacion": [20, 50, 100, 200],
    "k": [2, 3, 5, 7],
    "pc": [0.5, 0.7, 0.9, 1.0],
    "elites": [1, 2, 5],
}


def run_config(args):
    nombre, valor, params, tope, semillas = args
    colocadas, ocupadas, ultima = [], [], []
    for (n, k, m), semilla_inst in itertools.product(TRAIN_CONFIGS, TRAIN_SEEDS):
        inst = parse_instance(generate(n, k, m, semilla_inst))
        agente = AgenteEvolutivo(
            poblacion=params["poblacion"],
            pm_factor=params["pm_factor"],
            pc=params["pc"],
            k=params["k"],
            elites=params["elites"],
            paciencia_fraccion=1.0,  # sin estancamiento: presupuesto fijo
            tope_evaluaciones=tope,
        )
        for semilla in semillas:
            resultado = agente.solve(inst, semilla, Deadline(float("inf")))
            estado = GameState(inst)
            for fila, col in resultado.placements:
                estado.place(fila, col)
            colocadas.append(estado.placed)
            ocupadas.append(estado.occupied)
            ultima.append(resultado.stats["evaluaciones_ultima_mejora"])
    return (nombre, valor, statistics.mean(colocadas), statistics.pstdev(colocadas),
            statistics.mean(ocupadas), statistics.pstdev(ocupadas), statistics.mean(ultima))


def main() -> int:
    parser = argparse.ArgumentParser(description="Barrido de parámetros del agente evolutivo.")
    parser.add_argument("--tope", type=int, default=100_000, help="evaluaciones por corrida")
    parser.add_argument("--semillas", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--solo", nargs="+", choices=list(SWEEP), help="barrer solo estos parámetros")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default="results/tuning_evolutivo.csv")
    args = parser.parse_args()

    etiquetas, unicos = [], {}  # la config BASE sale en cada barrido; se corre una sola vez
    for nombre, valores in SWEEP.items():
        if args.solo and nombre not in args.solo:
            continue
        for valor in valores:
            params = dict(BASE, **{nombre: valor})
            clave = tuple(sorted(params.items()))
            etiquetas.append((nombre, valor, clave))
            unicos.setdefault(clave, (nombre, valor, params, args.tope, args.semillas))

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        resultados = dict(zip(unicos, pool.map(run_config, unicos.values())))
    filas = [(nombre, valor) + resultados[clave][2:] for nombre, valor, clave in etiquetas]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["parametro", "valor", "colocadas_prom", "colocadas_desv",
                           "ocupadas_prom", "ocupadas_desv", "ultima_mejora_prom", "tope", "n_corridas"])
        n_corridas = len(TRAIN_CONFIGS) * len(TRAIN_SEEDS) * len(args.semillas)
        for nombre, valor, cp, cd, op, od, um in filas:
            escritor.writerow([nombre, valor, f"{cp:.2f}", f"{cd:.2f}", f"{op:.2f}", f"{od:.2f}", f"{um:.0f}",
                               args.tope, n_corridas])

    print(f"tope={args.tope}  semillas={args.semillas}  base={BASE}")
    for nombre in (args.solo or SWEEP):
        print(f"\n{nombre}:")
        grupo = [f for f in filas if f[0] == nombre]
        for _, valor, cp, cd, op, od, um in sorted(grupo, key=lambda f: (-f[2], f[4])):
            print(f"  {valor!s:<6} colocadas={cp:7.2f} (±{cd:5.2f})  ocupadas={op:6.2f} (±{od:5.2f})"
                  f"  ult.mejora={um:8.0f}")
    print(f"\nresultados en {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())