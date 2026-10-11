"""Ejecuta los agentes sobre instancias y valida cada solución, de punta a punta.

    python run_all.py                                  # ambos agentes sobre instances/*.txt
    python run_all.py instances/ejemplo.txt            # una instancia
    python run_all.py instances/comparacion --seeds 1 2 3 --time-limit 10
    python run_all.py --agents busqueda --tests        # corre antes las pruebas

Alternativa portable al Makefile: solo necesita Python (no requiere ``make``, que no viene en Windows).

Por cada combinación instancia x agente x semilla hace exactamente lo que haría el evaluador:
1. ``python -m tileup solve ...`` escribe la solución e informa métricas por salida estándar;
2. ``python -m validator ...`` reproduce la partida de forma independiente;
3. comprueba que la solución sea VALIDA, que las métricas del programa y del validador coincidan
   y que el tiempo real (incluido el arranque de Python) no exceda el límite.

Imprime una tabla, escribe un resumen CSV y termina con código 1 si alguna corrida falla.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_AGENTS = ["busqueda", "evolutivo"]
METRICS = ("colocadas", "ocupadas", "mayor")


def collect_instances(paths: list[str]) -> list[Path]:
    """Expande carpetas a sus .txt; excluye los archivos de solución de ejemplo."""
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found += sorted(p for p in path.glob("*.txt") if not p.stem.endswith("_solucion"))
        elif path.is_file():
            found.append(path)
        else:
            sys.exit(f"error: no existe {raw}")
    if not found:
        sys.exit("error: no se encontraron instancias")
    return found


def parse_metrics(text: str) -> dict[str, str]:
    return dict(re.findall(r"(\w+)=(\S+)", text))


def run(args: list[str], timeout: float) -> tuple[subprocess.CompletedProcess, float]:
    start = time.perf_counter()
    proc = subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=ROOT, timeout=timeout)
    return proc, time.perf_counter() - start


def run_one(instance: Path, agent: str, seed: int, limit: float, out_dir: Path) -> dict:
    solution = out_dir / f"{instance.stem}.{agent}.s{seed}.txt"
    row = {"instancia": instance.as_posix(), "agente": agent, "semilla": seed, "estado": "OK", "detalle": ""}

    try:
        solve, wall = run(["-m", "tileup", "solve", str(instance), "--agent", agent, "--seed", str(seed),
                           "--time-limit", str(limit), "--out", str(solution)], timeout=limit * 3 + 30)
    except subprocess.TimeoutExpired:
        return {**row, "estado": "FALLO", "detalle": "el agente no terminó (colgado)"}
    row["tiempo_real"] = f"{wall:.2f}"
    if solve.returncode != 0:
        last_line = solve.stderr.strip().splitlines()[-1:] or [f"código de salida {solve.returncode}"]
        return {**row, "estado": "FALLO", "detalle": last_line[0][:160]}

    reported = parse_metrics(solve.stdout)
    row.update({k: reported.get(k, "") for k in (*METRICS, "resultado")})
    row["tiempo_agente"] = reported.get("tiempo", "").rstrip("s")
    effort_key = next((k for k in reported if k not in (*METRICS, "resultado", "tiempo", "agente", "semilla",
                                                        "limite", "instancia", "solucion")), "")
    row["esfuerzo"] = f"{effort_key}={reported[effort_key]}" if effort_key else ""

    check, _ = run(["-m", "validator", str(instance), str(solution)], timeout=120)
    validated = parse_metrics(check.stdout)
    problems = []
    if check.returncode != 0:
        problems.append("validador: " + " | ".join(l.strip() for l in check.stdout.splitlines() if l.strip().startswith("-"))
                        or check.stderr.strip())
    mismatched = [k for k in METRICS if reported.get(k) != validated.get(k)]
    if mismatched:
        problems.append("métricas distintas: " + ", ".join(f"{k} {reported.get(k)}≠{validated.get(k)}" for k in mismatched))
    if wall > limit:
        problems.append(f"excedió el límite ({wall:.2f}s > {limit}s)")
    if problems:
        row.update(estado="FALLO", detalle="; ".join(problems)[:200])
    return row


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Ejecuta los agentes y valida sus soluciones.")
    parser.add_argument("instances", nargs="*", default=["instances"], help="archivos o carpetas (por defecto instances/)")
    parser.add_argument("--agents", nargs="+", default=DEFAULT_AGENTS, help="agentes a ejecutar")
    parser.add_argument("--seeds", nargs="+", type=int, default=[1], help="semillas por agente")
    parser.add_argument("--time-limit", type=float, default=10.0, help="límite por corrida, en segundos")
    parser.add_argument("--out-dir", default="solutions", help="carpeta de las soluciones")
    parser.add_argument("--summary", default=None, help="CSV de resumen (por defecto <out-dir>/resumen.csv)")
    parser.add_argument("--tests", action="store_true", help="corre las pruebas automatizadas antes")
    args = parser.parse_args()

    if args.tests:
        print("== Pruebas automatizadas ==", flush=True)
        tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ROOT)
        if tests.returncode != 0:
            print("Las pruebas fallaron; no se ejecutan los agentes.")
            return 1
        print()

    instances = collect_instances(args.instances)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(instances) * len(args.agents) * len(args.seeds)
    print(f"== {total} corridas: {len(instances)} instancias x {args.agents} x semillas {args.seeds}, "
          f"límite {args.time_limit}s ==")
    header = f"{'instancia':<28} {'agente':<10} {'sem':>3} {'coloc':>6} {'ocup':>5} {'mayor':>6} {'tiempo':>7}  estado"
    print(header)
    print("-" * len(header))

    rows = []
    for instance in instances:
        for agent in args.agents:
            for seed in args.seeds:
                row = run_one(instance, agent, seed, args.time_limit, out_dir)
                rows.append(row)
                status = "VALIDA" if row["estado"] == "OK" else f"FALLO: {row['detalle']}"
                print(f"{instance.stem[:28]:<28} {agent:<10} {seed:>3} {row.get('colocadas', '-'):>6} "
                      f"{row.get('ocupadas', '-'):>5} {row.get('mayor', '-'):>6} {row.get('tiempo_real', '-'):>6}s  {status}",
                      flush=True)

    summary = Path(args.summary) if args.summary else out_dir / "resumen.csv"
    fields = ["instancia", "agente", "semilla", "colocadas", "ocupadas", "mayor", "resultado",
              "tiempo_agente", "tiempo_real", "esfuerzo", "estado", "detalle"]
    with summary.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    failed = [r for r in rows if r["estado"] != "OK"]
    print()
    print(f"{total - len(failed)}/{total} corridas válidas y dentro del límite. Resumen: {summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
