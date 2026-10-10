"""Contrato común de los agentes.

Un agente recibe la instancia (inmutable), una semilla y un ``Deadline``, y devuelve la
lista de colocaciones (fila, columna) que propone. El programa principal vuelve a aplicar
esas colocaciones sobre un ``GameState`` nuevo del motor, de modo que ningún agente puede
alterar las reglas: una jugada ilegal se detecta y se reporta como error del agente.

Para agregar un agente:

    from tileup.agents.base import Agent, AgentResult, register

    @register
    class MiAgente(Agent):
        name = "mi_agente"
        effort_name = "nodos_expandidos"
        def solve(self, instance, seed, deadline): ...
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..engine import Instance

AGENTS: dict[str, type[Agent]] = {}


def register(cls: type[Agent]) -> type[Agent]:
    if cls.name in AGENTS:
        raise ValueError(f"agente duplicado: {cls.name}")
    AGENTS[cls.name] = cls
    return cls


class Deadline:
    """Límite de tiempo absoluto, medido con un reloj monotónico."""

    def __init__(self, seconds: float, start: float | None = None) -> None:
        self.start = time.perf_counter() if start is None else start
        self.end = self.start + seconds

    def expired(self) -> bool:
        return time.perf_counter() >= self.end

    def remaining(self) -> float:
        return max(0.0, self.end - time.perf_counter())

    def elapsed(self) -> float:
        return time.perf_counter() - self.start


@dataclass
class AgentResult:
    placements: list[tuple[int, int]]
    effort: int  # medida de esfuerzo propia del algoritmo
    stats: dict[str, object] = field(default_factory=dict)  # métricas adicionales opcionales


class Agent(ABC):
    name: str = ""
    effort_name: str = "esfuerzo"

    @abstractmethod
    def solve(self, instance: Instance, seed: int, deadline: Deadline) -> AgentResult:
        """Debe devolver la mejor solución encontrada antes de ``deadline``."""


"""Archivo generado por inteligencia artificial """