"""Seleccion de oportunidades y cruce con preferencias de clientes."""

from __future__ import annotations

import ast
import re
import unicodedata
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .config import PROJECT_ROOT, ProjectPaths, load_project_config
from .domain.clients import validate_clients
from .domain.properties import validate_predictions
from .storage import read_csv, write_csv_atomic


@lru_cache(maxsize=8)
def _rules(path: str) -> dict:
    return load_project_config(Path(path))


def _default_rules() -> dict:
    return _rules(str(PROJECT_ROOT / "config" / "matching_rules.yaml"))


def _normalise(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(char for char in text if not unicodedata.combining(char)).strip().lower()


def _items(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _condition(value: object) -> str:
    normalised = _normalise(value)
    return {
        "promocion de obra nueva": "obra nueva",
    }.get(normalised, normalised)


def _enabled(value: object) -> bool:
    if pd.isna(value):
        return False
    accepted = set(_default_rules().get("selected_values", []))
    return _normalise(value) in accepted


def opportunity_threshold(price: float, area: object, rules: dict | None = None) -> float:
    rules = rules or _default_rules()
    location = _normalise(area)
    groups = rules["thresholds"]
    group = next(
        (
            settings
            for name, settings in groups.items()
            if name != "default"
            and location in {_normalise(item) for item in settings.get("areas", [])}
        ),
        groups["default"],
    )
    ratio = float(group.get("default_ratio", 0))
    for band in group.get("bands", []):
        minimum_matches = (
            "min_price_inclusive" not in band
            or price >= float(band["min_price_inclusive"])
        )
        maximum_matches = (
            (
                "max_price_exclusive" not in band
                or price < float(band["max_price_exclusive"])
            )
            and (
                "max_price_inclusive" not in band
                or price <= float(band["max_price_inclusive"])
            )
        )
        if minimum_matches and maximum_matches:
            ratio = float(band["ratio"])
            break
    return max(0.0, price * ratio)


def _client_matches(properties: pd.DataFrame, client: pd.Series) -> pd.Series:
    matches = pd.Series(True, index=properties.index, dtype=bool)

    numeric_filters = {
        "precio_min": ("Precio", "min"),
        "precio_max": ("Precio", "max"),
        "m2_min": ("m2_utiles", "min"),
        "m2_max": ("m2_utiles", "max"),
        "planta_min": ("planta_numero", "min"),
        "planta_max": ("planta_numero", "max"),
        "habitaciones_min": ("habitaciones", "min"),
        "baños_min": ("banos", "min"),
    }
    for client_column, (property_column, bound) in numeric_filters.items():
        if client_column not in client or pd.isna(client[client_column]):
            continue
        if property_column not in properties:
            return pd.Series(False, index=properties.index, dtype=bool)
        values = pd.to_numeric(properties[property_column], errors="coerce")
        requested = float(client[client_column])
        matches &= values >= requested if bound == "min" else values <= requested

    if "exterior" in client and _enabled(client["exterior"]):
        matches &= properties.get("Exterior", pd.Series(0, index=properties.index)).eq(1)

    areas = [_normalise(value) for value in _items(client.get("barrios_interes"))]
    if areas:
        locations = properties["Localizacion"].fillna("").map(_normalise)
        matches &= locations.apply(
            lambda location: any(area in location for area in areas)
        )

    conditions = [_condition(value) for value in _items(client.get("estados_vivienda"))]
    if conditions:
        matches &= properties["estado_vivienda"].fillna("").map(_condition).isin(conditions)

    for extra in _items(client.get("extras")):
        column = _normalise(extra).replace(" ", "_")
        if column not in properties:
            matches &= False
        else:
            matches &= pd.to_numeric(properties[column], errors="coerce").fillna(0).eq(1)

    return matches


def match_clients(
    predictions: pd.DataFrame,
    clients: pd.DataFrame,
    new_ids: Iterable[int],
    rules: dict | None = None,
) -> pd.DataFrame:
    validate_predictions(predictions)
    validate_clients(clients)
    rules = rules or _default_rules()

    ids = {int(value) for value in new_ids}
    candidates = predictions.copy()
    candidates["id"] = pd.to_numeric(candidates["id"], errors="coerce").astype("Int64")
    candidates = candidates[candidates["id"].isin(ids)].copy()
    if candidates.empty:
        return candidates.assign(
            Umbral=pd.Series(dtype=float),
            Clientes_Interesados=pd.Series(dtype=object),
            Seleccionado=pd.Series(dtype=bool),
            Enlace=pd.Series(dtype=str),
        )

    candidates["Umbral"] = candidates.apply(
        lambda row: opportunity_threshold(
            float(row["Precio"]), row["Localizacion"], rules
        ),
        axis=1,
    )
    prices = pd.to_numeric(candidates["Precio"], errors="coerce")
    differences = pd.to_numeric(
        candidates["Diferencia_Ponderada"], errors="coerce"
    )
    minimum_price = float(rules.get("candidate_price_min", 90_000))
    maximum_price = float(rules.get("candidate_price_max", 500_000))
    candidates = candidates[
        differences.gt(candidates["Umbral"])
        & prices.between(minimum_price, maximum_price, inclusive="both")
    ].copy()

    interested: dict[int, list[object]] = {}
    for _, client in clients.iterrows():
        for index in candidates.index[_client_matches(candidates, client)]:
            interested.setdefault(index, []).append(client["id"])

    candidates["Clientes_Interesados"] = candidates.index.map(
        lambda index: interested.get(index, [])
    )
    candidates = candidates[candidates["Clientes_Interesados"].map(bool)].copy()
    candidates["Seleccionado"] = False
    candidates["Enlace"] = (
        "https://www.idealista.com/inmueble/" + candidates["id"].astype(str) + "/"
    )
    return candidates.reset_index(drop=True)


def parse_interested_clients(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    if pd.isna(value) or not str(value).strip():
        return []
    try:
        parsed = ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        parsed = [item for item in re.split(r"[,;]", str(value)) if item.strip()]
    if not isinstance(parsed, (list, tuple, set)):
        parsed = [parsed]
    return [str(item) for item in parsed]


def selected_properties(review: pd.DataFrame) -> pd.DataFrame:
    if "Seleccionado" not in review:
        raise ValueError("El CSV de revision no contiene la columna Seleccionado")
    enabled = review["Seleccionado"].map(_enabled)
    return review[enabled].copy()


def read_review(path: Path) -> pd.DataFrame:
    """Lee el CSV aunque Numbers/Excel cambie `;` por `,` al guardarlo."""

    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de revision: {path}")
    return pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")


def run_matching(paths: ProjectPaths, new_ids: Iterable[int]) -> pd.DataFrame:
    predictions = read_csv(paths.predictions)
    clients = read_csv(paths.clients)
    rules = _rules(str(paths.matching_rules))
    review = match_clients(predictions, clients, new_ids, rules)
    if not review.empty and paths.raw_properties.exists():
        raw = read_csv(paths.raw_properties, encoding="utf-16")
        if "Titulo" in raw:
            titles = raw[["id", "Titulo"]].copy()
            titles["id"] = pd.to_numeric(titles["id"], errors="coerce").astype(
                "Int64"
            )
            titles = titles.dropna(subset=["id"]).drop_duplicates(
                subset="id", keep="last"
            )
            review = review.merge(titles, on="id", how="left")
    write_csv_atomic(review, paths.review)
    return review
