"""Fuente determinista para pruebas y demostraciones sin red."""

from __future__ import annotations

from collections.abc import Iterable

from ..domain.properties import RawProperty


class FixtureSource:
    name = "fixture"

    def __init__(self, properties: Iterable[RawProperty]):
        self._properties = list(properties)

    def collect_new(self, known_ids: set[int]) -> list[RawProperty]:
        return [item for item in self._properties if item.id not in known_ids]
