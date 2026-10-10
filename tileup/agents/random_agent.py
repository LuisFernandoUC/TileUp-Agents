"""Agente de referencia: coloca cada ficha en una celda vacía elegida al azar.

Agente aleatorio (No greedy ni ni picha xd)
"""

from __future__ import annotations

import random

from ..engine import GameState, Instance
from .base import Agent, AgentResult, Deadline, register


@register
class RandomAgent(Agent):
    name = "aleatorio"
    effort_name = "jugadas_evaluadas"

    def solve(self, instance: Instance, seed: int, deadline: Deadline) -> AgentResult:
        rng = random.Random(seed)
        state = GameState(instance)
        while not state.is_terminal and not deadline.expired():
            cell = rng.choice(state.empty_cells())
            state.place(*divmod(cell, state.n))
        return AgentResult(placements=state.placements, effort=state.placed)
