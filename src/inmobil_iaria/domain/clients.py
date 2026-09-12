"""Contrato de preferencias privadas de clientes."""

from __future__ import annotations

import pandas as pd


def validate_clients(dataframe: pd.DataFrame) -> pd.DataFrame:
    if "id" not in dataframe.columns:
        raise ValueError("El archivo de clientes debe contener la columna id")
    if dataframe["id"].isna().any() or dataframe["id"].astype(str).duplicated().any():
        raise ValueError("El archivo de clientes contiene IDs vacios o duplicados")
    return dataframe
