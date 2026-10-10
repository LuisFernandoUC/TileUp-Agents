"""Registro de agentes. Importar un módulo de agente lo registra en ``AGENTS``."""

from . import random_agent  # noqa: F401  (registro por efecto secundario)
from .base import AGENTS, Agent, AgentResult, Deadline, register

__all__ = ["AGENTS", "Agent", "AgentResult", "Deadline", "register"]
