"""Punto de extension para la Search API oficial de Idealista."""

from __future__ import annotations

from ..domain.properties import RawProperty


class IdealistaApiSource:
    name = "idealista_api"

    def __init__(self, api_key: str | None, api_secret: str | None):
        self.api_key = api_key
        self.api_secret = api_secret

    def collect_new(self, known_ids: set[int]) -> list[RawProperty]:
        if not self.api_key or not self.api_secret:
            raise RuntimeError(
                "Configura credenciales de la API oficial antes de usar idealista_api"
            )
        raise NotImplementedError(
            "El adaptador se activara cuando exista acceso autorizado a la Search API"
        )
