"""Pruebas del núcleo del agente evolutivo: decodificación, reparación, aptitud y evaluador."""

from __future__ import annotations

import random
import unittest
from pathlib import Path

from tileup.agents.evolutivo import (
    DECODIFICADORES,
    Evaluador,
    aptitud_de,
    decodificar_a,
    decodificar_c,
    genoma_aleatorio,
)
from tileup.engine import EMPTY, GameState, Instance, Tile
from tileup.instance import load_instance

INSTANCES = Path(__file__).resolve().parent.parent / "instances"


def _cargar(nombre: str) -> Instance:
    return load_instance(INSTANCES / nombre)


class DecodificacionTest(unittest.TestCase):
    def test_sin_reparacion_reproduce_el_ejemplo_del_enunciado(self) -> None:
        # Celdas (fila*4+col) de la solución del enunciado: (0,0) (1,1) (0,1) (2,2) (0,2) (1,2).
        instancia = _cargar("ejemplo.txt")
        state = decodificar_a(instancia, [0, 5, 1, 10, 2, 6])
        self.assertEqual(state.placements, [(0, 0), (1, 1), (0, 1), (2, 2), (0, 2), (1, 2)])
        self.assertEqual(aptitud_de(state), (6, -3))
        self.assertEqual(state.max_value, 6)

    def test_la_reparacion_avanza_a_la_siguiente_celda_libre(self) -> None:
        instancia = Instance(n=2, k=3, tiles=(Tile(1, 1), Tile(2, 1), Tile(3, 1)))
        state = decodificar_a(instancia, [0, 0, 3])
        # El segundo gen apunta a la celda 0 (ocupada) y se repara a la 1.
        self.assertEqual(state.placements, [(0, 0), (0, 1), (1, 1)])

    def test_la_reparacion_da_la_vuelta_al_final_del_tablero(self) -> None:
        instancia = Instance(n=2, k=2, tiles=(Tile(1, 1), Tile(2, 1)))
        state = decodificar_a(instancia, [3, 3])
        # La celda 3 está ocupada; (3 + 1) % 4 = 0.
        self.assertEqual(state.placements, [(1, 1), (0, 0)])

    def test_derrota_termina_con_tablero_lleno_y_ignora_genes_sobrantes(self) -> None:
        instancia = _cargar("derrota_inevitable.txt")
        state = decodificar_a(instancia, [0, 1, 2, 3, 0])
        self.assertEqual(state.placed, 4)
        self.assertEqual(state.occupied, 4)
        self.assertEqual(aptitud_de(state), (4, -4))

    def test_longitud_incorrecta_se_rechaza(self) -> None:
        instancia = _cargar("ejemplo.txt")
        with self.assertRaises(ValueError):
            decodificar_a(instancia, [0, 1, 2])


class AptitudTest(unittest.TestCase):
    def test_ganar_supera_a_perder_y_menos_ocupadas_supera_a_mas(self) -> None:
        victoria_despejada = (6, -3)
        victoria_llena = (6, -4)
        derrota = (4, -4)
        self.assertGreater(victoria_despejada, victoria_llena)
        self.assertGreater(victoria_llena, derrota)

    def test_el_estado_de_un_genoma_ganador_puntua_mas_que_el_de_uno_perdedor(self) -> None:
        instancia = _cargar("ejemplo.txt")
        ganador = aptitud_de(decodificar_a(instancia, [0, 5, 1, 10, 2, 6]))
        perdedor = aptitud_de(decodificar_a(_cargar("derrota_inevitable.txt"), [0, 1, 2, 3, 0]))
        self.assertGreater(ganador, perdedor)


class PropiedadesTest(unittest.TestCase):
    """Cualquier genoma aleatorio debe dar una partida legal y reproducible."""

    NOMBRES = [
        "ejemplo.txt",
        "derrota_inevitable.txt",
        "gen_n4_k3_m30.txt",
        "gen_n4_k9_m50.txt",
        "gen_n6_k20_m120.txt",
    ]

    def test_cualquier_genoma_aleatorio_produce_una_partida_legal(self) -> None:
        rng = random.Random(0)
        for nombre in self.NOMBRES:
            instancia = _cargar(nombre)
            for _ in range(100):
                genoma = genoma_aleatorio(rng, instancia)
                state = decodificar_a(instancia, genoma)
                self.assertEqual(len(state.placements), state.placed)
                # Repetir las colocaciones sobre un tablero nuevo falla si alguna fuera ilegal.
                replay = GameState(instancia)
                for fila, col in state.placements:
                    replay.place(fila, col)
                self.assertEqual(replay.colors, state.colors)
                self.assertEqual(replay.values, state.values)
                self.assertEqual(state.occupied, sum(1 for c in state.colors if c != EMPTY))

    def test_decodificar_dos_veces_da_lo_mismo(self) -> None:
        rng = random.Random(1)
        instancia = _cargar("gen_n6_k20_m120.txt")
        genoma = genoma_aleatorio(rng, instancia)
        a = decodificar_a(instancia, genoma)
        b = decodificar_a(instancia, genoma)
        self.assertEqual(a.placements, b.placements)
        self.assertEqual(aptitud_de(a), aptitud_de(b))

    def test_el_genoma_aleatorio_depende_solo_de_la_semilla_y_esta_en_rango(self) -> None:
        instancia = _cargar("gen_n4_k9_m50.txt")
        g1 = genoma_aleatorio(random.Random(7), instancia)
        g2 = genoma_aleatorio(random.Random(7), instancia)
        g3 = genoma_aleatorio(random.Random(8), instancia)
        self.assertEqual(g1, g2)
        self.assertNotEqual(g1, g3)
        self.assertEqual(len(g1), instancia.m)
        self.assertTrue(all(0 <= g < instancia.n**2 for g in g1))


class EvaluadorTest(unittest.TestCase):
    def test_cuenta_solo_las_evaluaciones_y_no_las_jugadas_finales(self) -> None:
        instancia = _cargar("gen_n4_k9_m50.txt")
        rng = random.Random(3)
        evaluador = Evaluador(instancia)
        for _ in range(3):
            evaluador.evaluar(genoma_aleatorio(rng, instancia))
        self.assertEqual(evaluador.evaluaciones, 3)
        evaluador.jugar(genoma_aleatorio(rng, instancia))
        self.assertEqual(evaluador.evaluaciones, 3)

    def test_el_mismo_genoma_da_siempre_la_misma_aptitud(self) -> None:
        instancia = _cargar("gen_n4_k9_m50.txt")
        genoma = genoma_aleatorio(random.Random(5), instancia)
        evaluador = Evaluador(instancia)
        self.assertEqual(evaluador.evaluar(genoma), evaluador.evaluar(genoma))


if __name__ == "__main__":
    unittest.main()


class DecodificadorGuiadoTest(unittest.TestCase):
    """El decodificador C prefiere las celdas donde la ficha se fusiona."""

    def test_con_una_celda_que_fusiona_el_gen_la_elige_entre_las_candidatas(self) -> None:
        instancia = Instance(n=3, k=1, tiles=(Tile(1, 1), Tile(1, 1)))
        # La 1.ª ficha va al centro (celda 4). Para la 2.ª, el gen 8 en A iría a la esquina sin fusionar;
        # en C solo se consideran las vecinas del centro (1, 3, 5, 7) y el gen 8 elige la 1.ª (celda 1).
        a = decodificar_a(instancia, [4, 8])
        c = decodificar_c(instancia, [4, 8])
        self.assertEqual(a.occupied, 2)
        self.assertEqual(c.occupied, 1)
        self.assertEqual(c.values[1], 2)  # la ficha fusionada queda en la celda recién colocada

    def test_todos_los_decodificadores_dan_partidas_legales(self) -> None:
        rng = random.Random(3)
        for nombre in ("ejemplo.txt", "derrota_inevitable.txt", "gen_n4_k9_m50.txt", "gen_n6_k20_m120.txt"):
            instancia = _cargar(nombre)
            for decodificar in DECODIFICADORES.values():
                for _ in range(30):
                    state = decodificar(instancia, genoma_aleatorio(rng, instancia))
                    replay = GameState(instancia)
                    for fila, col in state.placements:
                        replay.place(fila, col)
                    self.assertEqual(replay.colors, state.colors)
                    self.assertEqual(state.occupied, sum(1 for c in state.colors if c != EMPTY))

    def test_suma_ocupacion_acumula_las_celdas_ocupadas_tras_cada_jugada(self) -> None:
        instancia = Instance(n=3, k=1, tiles=(Tile(1, 1), Tile(1, 1)))
        suma = [0]
        decodificar_c(instancia, [4, 8], suma)
        self.assertEqual(suma[0], 1 + 1)  # tras la 1.ª: 1 ocupada; tras fusionar la 2.ª: 1 ocupada
