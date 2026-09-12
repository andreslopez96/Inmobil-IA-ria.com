"""Prediccion de precios con una unica preparacion de variables."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import ProjectPaths, load_project_config
from .domain.properties import validate_predictions, validate_processed
from .storage import read_csv, write_csv_atomic


@dataclass(frozen=True)
class ModelSpec:
    model: Path
    metadata: Path
    output: str
    inverse_mse: float


def model_specs(paths: ProjectPaths) -> tuple[ModelSpec, ...]:
    registry = load_project_config(paths.model_registry)
    specs: list[ModelSpec] = []
    for item in registry.get("models", []):
        if not item.get("active", False):
            continue
        metadata = paths.model_metadata(item["directory"], item["legacy_columns"])
        mse = _metadata_mse(metadata, item.get("legacy_mse"))
        if mse is None or mse <= 0:
            raise ValueError(f"MSE no valido para el modelo {item['name']}")
        specs.append(
            ModelSpec(
                paths.model_file(item["legacy_model"]),
                metadata,
                item["output"],
                1 / mse,
            )
        )
    if not specs:
        raise ValueError("El registro no contiene modelos activos")
    return tuple(specs)


def _metadata_mse(path: Path, legacy_mse: object = None) -> float | None:
    if path.suffix == ".json" and path.exists():
        metadata = json.loads(path.read_text(encoding="utf-8"))
        value = metadata.get("metrics", {}).get("mse")
        return float(value) if value is not None else None
    return float(legacy_mse) if legacy_mse is not None else None


def _feature_columns(path: Path) -> list[str]:
    if path.suffix == ".json":
        metadata = json.loads(path.read_text(encoding="utf-8"))
        columns = metadata.get("feature_columns")
        if not isinstance(columns, list) or not columns:
            raise ValueError(f"Metadatos sin feature_columns: {path}")
        return [str(column) for column in columns]
    return [str(column) for column in joblib.load(path)]


def _fill_missing(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    numeric = result.select_dtypes(include=[np.number]).columns
    categorical = result.select_dtypes(exclude=[np.number]).columns
    result[numeric] = result[numeric].fillna(result[numeric].mean())
    result[categorical] = result[categorical].fillna("Desconocido")
    return result


def predict_properties(
    properties: pd.DataFrame, specs: tuple[ModelSpec, ...]
) -> pd.DataFrame:
    if properties.empty:
        raise ValueError("No hay inmuebles procesados para predecir")
    validate_processed(properties)

    result = _fill_missing(properties)
    features = pd.get_dummies(result.drop(columns=["Precio", "id"], errors="ignore"))

    for spec in specs:
        if not spec.model.exists() or not spec.metadata.exists():
            raise FileNotFoundError(
                f"Falta el modelo o sus metadatos: {spec.model}, {spec.metadata}"
            )
        model = joblib.load(spec.model)
        training_columns = _feature_columns(spec.metadata)
        aligned = features.reindex(columns=training_columns, fill_value=0)
        result[spec.output] = model.predict(aligned)

    weight_sum = sum(spec.inverse_mse for spec in specs)
    estimated_price = sum(
        result[spec.output] * (spec.inverse_mse / weight_sum) for spec in specs
    )
    result["Diferencia_Ponderada"] = estimated_price - result["Precio"]
    result["Diferencia_Ponderada"] = result["Diferencia_Ponderada"].fillna(0)

    prediction_columns = [spec.output for spec in specs]
    columns = list(result.columns)
    price_index = columns.index("Precio")
    ordered = columns[: price_index + 1] + [
        "Diferencia_Ponderada",
        *prediction_columns,
    ] + [
        column
        for column in columns[price_index + 1 :]
        if column not in {"Diferencia_Ponderada", *prediction_columns}
    ]
    result = result.loc[:, ~result.columns.duplicated()].copy()
    result = result[ordered]
    result = result.drop_duplicates(subset="id", keep="last").reset_index(drop=True)
    validate_predictions(result)
    return result


def run_prediction(paths: ProjectPaths) -> pd.DataFrame:
    properties = read_csv(paths.processed_properties)
    predictions = predict_properties(properties, model_specs(paths))
    write_csv_atomic(predictions, paths.predictions)
    return predictions
