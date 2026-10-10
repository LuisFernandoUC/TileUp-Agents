"""Pruebas del lector de instancias, incluidos los archivos mal formados."""

import tempfile
import unittest
from pathlib import Path

from tileup.engine import Tile
from tileup.instance import InstanceError, load_instance, parse_instance

EXAMPLE = """# TileUp -- instancia de ejemplo
4 3   # tablero 4x4, 3 colores
6     # 6 fichas en la secuencia
1 2
2 1
1 3
3 1
1 1
2 4
"""


class ParseValidTest(unittest.TestCase):
    def test_example_from_statement(self):
        inst = parse_instance(EXAMPLE)
        self.assertEqual((inst.n, inst.k, inst.m), (4, 3, 6))
        self.assertEqual(inst.tiles[0], Tile(1, 2))
        self.assertEqual(inst.tiles[-1], Tile(2, 4))

    def test_blank_lines_comments_and_extra_spaces(self):
        text = "\n# encabezado\n\n  2   1  \n\n# M\n2\n\t1 3 \n# en medio\n1   4\n\n"
        inst = parse_instance(text)
        self.assertEqual(inst.tiles, (Tile(1, 3), Tile(1, 4)))

    def test_windows_line_endings(self):
        inst = parse_instance("2 1\r\n1\r\n1 1\r\n")
        self.assertEqual(inst.m, 1)

    def test_zero_tiles(self):
        self.assertEqual(parse_instance("3 2\n0\n").m, 0)

    def test_load_with_utf8_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bom.txt"
            path.write_bytes("﻿2 1\n1\n1 1\n".encode("utf-8"))
            self.assertEqual(load_instance(path).n, 2)


class ParseInvalidTest(unittest.TestCase):
    CASES = {
        "vacía": "",
        "solo comentarios": "# nada\n\n",
        "encabezado incompleto": "4\n1\n1 1\n",
        "encabezado con tres números": "4 3 2\n1\n1 1\n",
        "N no entero": "a 3\n1\n1 1\n",
        "N decimal": "4.5 3\n1\n1 1\n",
        "N cero": "0 3\n1\n1 1\n",
        "K cero": "4 0\n1\n1 1\n",
        "falta M": "4 3\n",
        "M negativo": "4 3\n-1\n",
        "M no entero": "4 3\nseis\n",
        "faltan fichas": "4 3\n3\n1 1\n2 2\n",
        "fichas de más": "4 3\n1\n1 1\n2 2\n",
        "ficha con un número": "4 3\n1\n1\n",
        "color cero": "4 3\n1\n0 1\n",
        "color mayor que K": "4 3\n1\n4 1\n",
        "valor cero": "4 3\n1\n1 0\n",
        "valor negativo": "4 3\n1\n1 -2\n",
    }

    def test_malformed_inputs_raise_instance_error(self):
        for name, text in self.CASES.items():
            with self.subTest(caso=name):
                with self.assertRaises(InstanceError):
                    parse_instance(text)

    def test_error_message_points_to_line(self):
        with self.assertRaises(InstanceError) as ctx:
            parse_instance("# c\n4 3\n2\n1 1\n9 1\n")
        self.assertIn("línea 5", str(ctx.exception))

    def test_missing_file(self):
        with self.assertRaises(InstanceError):
            load_instance("no/existe/instancia.txt")

    def test_binary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bin.txt"
            path.write_bytes(b"\xff\xfe\x00\x81")
            with self.assertRaises(InstanceError):
                load_instance(path)


if __name__ == "__main__":
    unittest.main()
