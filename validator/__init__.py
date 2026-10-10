"""Validador independiente: no comparte código con el motor ni con los agentes."""

from .core import Report, ValidationInputError, validate_files, validate_text

__all__ = ["Report", "ValidationInputError", "validate_files", "validate_text"]
