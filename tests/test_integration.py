"""Integración: cada agente registrado resuelve instancias pequeñas de punta a punta por la
CLI oficial, y el validador independiente acepta la solución con las mismas métricas."""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tileup.agents import AGENTS
from validator import validate_files

ROOT = Path(__file__).resolve().parent.parent
SMALL = ["ejemplo.txt", "colores_alternos.txt", "derrota_inevitable.txt", "gen_n3_k5_m25.txt"]


def run(*args):
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=120
    )


def metrics(stdout):
    return {k: v for k, v in re.findall(r"(\w+)=(\S+)", stdout)}


class SolveAndValidateTest(unittest.TestCase):
    TIME_LIMIT = "5"

    def test_every_agent_produces_legal_solutions(self):
        with tempfile.TemporaryDirectory() as tmp:
            for agent in sorted(AGENTS):
                for name in SMALL:
                    with self.subTest(agente=agent, instancia=name):
                        out = Path(tmp) / f"{agent}_{name}"
                        inst = ROOT / "instances" / name
                        proc = run("-m", "tileup", "solve", str(inst), "--agent", agent,
                                   "--seed", "1", "--time-limit", self.TIME_LIMIT, "--out", str(out))
                        self.assertEqual(proc.returncode, 0, proc.stderr)
                        m = metrics(proc.stdout)
                        self.assertLess(float(m["tiempo"].rstrip("s")), float(self.TIME_LIMIT))

                        report = validate_files(inst, out)
                        self.assertTrue(report.valid, report.errors)
                        self.assertEqual(int(m["colocadas"]), report.placed)
                        self.assertEqual(int(m["ocupadas"]), report.occupied)
                        self.assertEqual(int(m["mayor"]), report.largest)

                        cli = run("-m", "validator", str(inst), str(out))
                        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
                        self.assertIn("VALIDA", cli.stdout)

    def test_same_seed_same_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            for agent in sorted(AGENTS):
                with self.subTest(agente=agent):
                    outs = []
                    for i in range(2):
                        out = Path(tmp) / f"{agent}_{i}.txt"
                        run("-m", "tileup", "solve", "instances/gen_n4_k9_m50.txt", "--agent", agent,
                            "--seed", "42", "--time-limit", "10", "--out", str(out))
                        outs.append(out.read_text(encoding="utf-8"))
                    self.assertEqual(outs[0], outs[1])


class CliErrorsTest(unittest.TestCase):
    def test_unknown_agent(self):
        proc = run("-m", "tileup", "solve", "instances/ejemplo.txt", "--agent", "nope",
                   "--seed", "1", "--time-limit", "1")
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_malformed_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "mala.txt"
            bad.write_text("3 3\nx\n", encoding="utf-8")
            proc = run("-m", "tileup", "solve", str(bad), "--agent", "aleatorio", "--seed", "1", "--time-limit", "1")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("error:", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_validator_rejects_with_exit_code_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            sol = Path(tmp) / "sol.txt"
            sol.write_text("0 0 0\n1 0 0\n# colocadas=2 ocupadas=1 mayor=2\n", encoding="utf-8")
            proc = run("-m", "validator", "instances/ejemplo.txt", str(sol))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("INVALIDA", proc.stdout)


if __name__ == "__main__":
    unittest.main()
