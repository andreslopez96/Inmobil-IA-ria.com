"""Transformacion de anuncios sin efectos secundarios ocultos."""

from __future__ import annotations

import re

import pandas as pd

from .config import ProjectPaths
from .domain.properties import RAW_COLUMNS, validate_processed, validate_raw
from .storage import read_csv, write_csv_atomic


def _extract_square_metres(text: object) -> tuple[int | None, int | None]:
    value = str(text)
    built = re.search(r"(\d+)\s*m² construidos", value, flags=re.IGNORECASE)
    usable = re.search(r"(\d+)\s*m² útiles", value, flags=re.IGNORECASE)
    return (
        int(built.group(1)) if built else None,
        int(usable.group(1)) if usable else None,
    )


def _extract_rooms(text: object) -> tuple[int | None, int | None]:
    value = str(text)
    bedrooms = re.search(r"(\d+)\s*habitaci[oó]n(?:es)?", value, re.IGNORECASE)
    bathrooms = re.search(r"(\d+)\s*bañ(?:o|os)", value, re.IGNORECASE)
    return (
        int(bedrooms.group(1)) if bedrooms else None,
        int(bathrooms.group(1)) if bathrooms else None,
    )


def _property_condition(text: object) -> str | None:
    value = str(text).lower()
    if "segunda mano/buen estado" in value:
        return "Segunda mano/Buen estado"
    if "segunda mano/para reformar" in value:
        return "Segunda mano/Para reformar"
    if "promoción de obra nueva" in value:
        return "Obra nueva"
    return None


def transform_properties(raw: pd.DataFrame) -> pd.DataFrame:
    """Convierte anuncios de Idealista al esquema usado por los modelos."""

    validate_raw(raw)

    result = raw.copy()
    result = result.drop(columns=["Titulo"], errors="ignore")
    basics = result["Caracteristicas_basicas"].fillna("").astype(str)
    extras = result["Caracteristicas_extra"].fillna("").astype(str)

    result[["m2_construidos", "m2_utiles"]] = basics.apply(
        lambda value: pd.Series(_extract_square_metres(value))
    )
    result[["habitaciones", "banos"]] = basics.apply(
        lambda value: pd.Series(_extract_rooms(value))
    )
    result["estado_vivienda"] = basics.apply(_property_condition)

    binary_features = {
        "trastero": "trastero",
        "terraza": "terraza",
        "balcon": "balcón",
        "ascensor": "con ascensor",
        "armarios_empotrados": "armarios empotrados",
        "plaza_garaje": "garaje",
        "garaje_incluido": "incluida",
        "garaje_adicional": "adicionales",
        "adaptado_movilidad_reducida": "movilidad reducida",
    }
    lowered_basics = basics.str.lower()
    for column, keyword in binary_features.items():
        result[column] = lowered_basics.str.contains(keyword, regex=False).astype(int)

    result["Exterior"] = lowered_basics.str.contains("exterior", regex=False).astype(int)
    result["Interior"] = lowered_basics.str.contains("interior", regex=False).astype(int)

    for direction in ("este", "oeste", "norte", "sur"):
        result[f"orientacion_{direction}"] = lowered_basics.str.contains(
            direction, regex=False
        ).astype(int)

    result["Calefacción"] = (
        basics.str.extract(r"Calefacción ([^;]+)", expand=False)
        .fillna("sin calefacción")
    )
    result["ano_construccion"] = pd.to_numeric(
        lowered_basics.str.extract(r"construido en\s*(\d+)", expand=False),
        errors="coerce",
    ).astype("Int64")
    result["planta_numero"] = pd.to_numeric(
        basics.str.extract(r"Planta\s+(\d+)", expand=False), errors="coerce"
    ).astype("Int64")

    lowered_extras = extras.str.lower()
    for column, keyword in {
        "jardin": "jardín",
        "piscina": "piscina",
        "aire_acondicionado": "aire acondicionado",
        "zonas_verdes": "zonas verdes",
    }.items():
        result[column] = lowered_extras.str.contains(keyword, regex=False).astype(int)

    return result.drop(
        columns=["Caracteristicas_basicas", "Caracteristicas_extra"], errors="ignore"
    )


def merge_properties(
    existing: pd.DataFrame | None, new_batch: pd.DataFrame
) -> pd.DataFrame:
    """Une lotes por ID; el dato mas reciente sustituye al anterior."""

    if existing is None or existing.empty:
        combined = new_batch.copy()
    else:
        combined = pd.concat([existing, new_batch], ignore_index=True, sort=False)
    return combined.drop_duplicates(subset="id", keep="last").reset_index(drop=True)


def run_preprocessing(paths: ProjectPaths) -> pd.DataFrame:
    raw = read_csv(paths.raw_properties, encoding="utf-16")
    batch = transform_properties(raw)
    write_csv_atomic(batch, paths.processed_batch)

    existing = (
        read_csv(paths.processed_properties)
        if paths.processed_properties.exists()
        else None
    )
    combined = merge_properties(existing, batch)
    validate_processed(combined)
    write_csv_atomic(combined, paths.processed_properties)
    return combined
