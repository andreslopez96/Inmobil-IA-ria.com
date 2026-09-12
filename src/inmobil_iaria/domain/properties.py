"""Contratos de anuncios, inmuebles procesados y predicciones."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


RAW_COLUMNS = {
    "id",
    "Localizacion",
    "Precio",
    "Caracteristicas_basicas",
    "Caracteristicas_extra",
}
PROCESSED_COLUMNS = {"id", "Localizacion", "Precio", "m2_construidos", "m2_utiles"}
PREDICTION_COLUMNS = {
    "id",
    "Precio",
    "Localizacion",
    "Predicción_RF",
    "Predicción_Bagging",
    "Predicción_GB",
    "Diferencia_Ponderada",
}


@dataclass(frozen=True)
class RawProperty:
    id: int
    Titulo: str
    Localizacion: str
    Precio: int
    Caracteristicas_basicas: str = ""
    Caracteristicas_extra: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "RawProperty":
        return cls(
            id=int(value["id"]),
            Titulo=str(value.get("Titulo") or f"Inmueble {value['id']}"),
            Localizacion=str(value.get("Localizacion") or "Zaragoza"),
            Precio=int(value["Precio"]),
            Caracteristicas_basicas=str(value.get("Caracteristicas_basicas") or ""),
            Caracteristicas_extra=str(value.get("Caracteristicas_extra") or ""),
        )

    def as_record(self) -> dict[str, object]:
        return asdict(self)


def _validate(dataframe: pd.DataFrame, required: set[str], stage: str) -> pd.DataFrame:
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(
            f"Esquema invalido en {stage}; faltan columnas: "
            + ", ".join(sorted(missing))
        )
    if dataframe.empty:
        return dataframe
    ids = pd.to_numeric(dataframe["id"], errors="coerce")
    if ids.isna().any():
        raise ValueError(f"Esquema invalido en {stage}; hay IDs vacios o no numericos")
    if ids.duplicated().any():
        raise ValueError(f"Esquema invalido en {stage}; hay IDs duplicados")
    prices = pd.to_numeric(dataframe["Precio"], errors="coerce")
    if prices.isna().any() or prices.le(0).any():
        raise ValueError(f"Esquema invalido en {stage}; Precio debe ser positivo")
    return dataframe


def validate_raw(dataframe: pd.DataFrame) -> pd.DataFrame:
    return _validate(dataframe, RAW_COLUMNS, "anuncios sin procesar")


def validate_processed(dataframe: pd.DataFrame) -> pd.DataFrame:
    return _validate(dataframe, PROCESSED_COLUMNS, "inmuebles procesados")


def validate_predictions(dataframe: pd.DataFrame) -> pd.DataFrame:
    return _validate(dataframe, PREDICTION_COLUMNS, "predicciones")
