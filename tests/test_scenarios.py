"""Escenarios completos sobre los archivos de ``instances/`` y la CLI de juego manual."""

import itertools
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tileup.engine import GameState, Status
from tileup.instance import load_instance
from tileup.solution import format_solution

ROOT = Path(__file__).resolve().parent.parent
INSTANCES = ROOT / "instances"


def play_moves(name, moves):
    state = GameState(load_instance(INSTANCES / name))
    for r, c in moves:
        state.place(r, c)
    return state


class InstanceFilesTest(unittest.TestCase):
    def test_all_instance_files_parse(self):
        files = [p for p in INSTANCES.glob("*.txt") if not p.stem.endswith("_solucion")]
        self.assertGreaterEqual(len(files), 6)
        for path in files:
            with self.subTest(instancia=path.name):
                inst = load_instance(path)
                self.assertEqual(len(inst.tiles), inst.m)


class ScenarioTest(unittest.TestCase):
    def test_statement_example_reproduces_expected_solution(self):
        moves = [(0, 0), (1, 1), (0, 1), (2, 2), (0, 2), (1, 2)]
        state = play_moves("ejemplo.txt", moves)
        self.assertIs(state.status, Status.WON)
        expected = (INSTANCES / "ejemplo_solucion.txt").read_text(encoding="utf-8")
        self.assertEqual(format_solution(state), expected)

    def test_single_color_wins_with_one_occupied_cell(self):
        # Alternar entre dos celdas vecinas: cada ficha se fusiona con la anterior.
        moves = [(0, 0), (0, 1)] * 4
        state = play_moves("un_color.txt", moves)
        self.assertIs(state.status, Status.WON)
        self.assertEqual(state.occupied, 1)
        self.assertEqual(state.max_value, sum(range(1, 9)))

    def test_unavoidable_loss_in_every_order(self):
        cells = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for order in itertools.permutations(cells):
            state = play_moves("derrota_inevitable.txt", order)
            self.assertIs(state.status, Status.LOST)
            self.assertEqual(state.placed, 4)

    def test_one_by_one_board_loses_after_first_tile(self):
        state = play_moves("tablero_1x1.txt", [(0, 0)])
        self.assertIs(state.status, Status.LOST)
        self.assertTrue(format_solution(state).endswith("# colocadas=1 ocupadas=1 mayor=5\n"))

    def test_cross_merge_of_five(self):
        state = play_moves("fusion_cruz.txt", [(0, 1), (1, 0), (1, 2), (2, 1), (1, 1), (0, 0)])
        self.assertIs(state.status, Status.WON)
        self.assertEqual(state.cell(1, 1).value, 15)
        self.assertEqual(state.occupied, 2)

    def test_alternating_colors_good_plan_wins(self):
        # Cada color oscila entre dos celdas propias; el tablero nunca pasa de 2 fichas.
        color1 = itertools.cycle([(0, 0), (0, 1)])
        color2 = itertools.cycle([(2, 2), (2, 1)])
        moves = [next(color1) if i % 2 == 0 else next(color2) for i in range(14)]
        state = play_moves("colores_alternos.txt", moves)
        self.assertIs(state.status, Status.WON)
        self.assertEqual(state.occupied, 2)
        self.assertEqual(state.max_value, 7)

    def test_alternating_colors_bad_plan_loses(self):
        # Colocar en orden de lectura sin buscar fusiones: patrón de ajedrez, sin fusiones.
        moves = [(r, c) for r in range(3) for c in range(3)]
        state = play_moves("colores_alternos.txt", moves)
        self.assertIs(state.status, Status.LOST)
        self.assertEqual(state.placed, 9)


class PlayCliTest(unittest.TestCase):
    def run_cli(self, *args, stdin=""):
        return subprocess.run(
            [sys.executable, "-m", "tileup", *args],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=ROOT,
            timeout=30,
        )

    def test_manual_game_writes_solution(self):
        moves = "0 0\n1 1\n0 1\n9 9\n2 2\n0 2\n1 2\n"  # incluye una jugada ilegal que se rechaza
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sol.txt"
            proc = self.run_cli("play", "instances/ejemplo.txt", "--out", str(out), "--no-color", stdin=moves)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("VICTORIA", proc.stdout)
            self.assertIn("Jugada ilegal", proc.stdout)
            expected = (INSTANCES / "ejemplo_solucion.txt").read_text(encoding="utf-8")
            self.assertEqual(out.read_text(encoding="utf-8"), expected)

    def test_abandoned_game_writes_partial_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sol.txt"
            proc = self.run_cli("play", "instances/ejemplo.txt", "--out", str(out), stdin="0 0\nq\n")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out.read_text(encoding="utf-8"), "0 0 0\n# colocadas=1 ocupadas=1 mayor=2\n")

    def test_malformed_instance_gives_readable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "mala.txt"
            bad.write_text("4 3\n2\n1 1\n", encoding="utf-8")
            proc = self.run_cli("play", str(bad))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("error:", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
