"""Contratos del dominio compartidos por todas las etapas."""

from .clients import validate_clients
from .properties import RawProperty, validate_predictions, validate_processed, validate_raw

__all__ = [
    "RawProperty",
    "validate_clients",
    "validate_predictions",
    "validate_processed",
    "validate_raw",
]
