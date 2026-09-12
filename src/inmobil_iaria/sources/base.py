"""Interfaz que desacopla el workflow del navegador o de ficheros."""

from __future__ import annotations

from typing import Protocol

from ..domain.properties import RawProperty


class PropertySource(Protocol):
    name: str

    def collect_new(self, known_ids: set[int]) -> list[RawProperty]: ...
