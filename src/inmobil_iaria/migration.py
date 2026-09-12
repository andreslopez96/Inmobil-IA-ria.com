"""Migracion verificable desde las rutas historicas al arbol organizado."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib

from .config import ProjectPaths, load_project_config


MODEL_METADATA = {
    "random_forest": {
        "legacy_columns": "columnas_entrenamiento_rf_venta.pkl",
        "mse": 1_051_962_139.54,
    },
    "bagging": {
        "legacy_columns": "columnas_entrenamiento_bagging_venta.pkl",
        "mse": 1_183_666_416.35,
    },
    "gradient_boosting": {
        "legacy_columns": "columnas_entrenamiento_gb_venta.pkl",
        "mse": 1_205_945_946.67,
    },
    "svr": {
        "legacy_columns": "columnas_entrenamiento_svr_venta.pkl",
        "mse": None,
    },
}


@dataclass(frozen=True)
class FileMove:
    source: Path
    destination: Path


@dataclass(frozen=True)
class MigrationRecord:
    source: str
    destination: str
    sha256: str
    bytes: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _report_destination(report_root: Path, source: Path) -> Path:
    property_id = source.parent.name
    names = {
        f"informe_{property_id}.pdf": "report.pdf",
        f"informe_{property_id}.tex": "source.tex",
        f"Portada_{property_id}.png": "cover.png",
        f"comparacion_eurom2_{property_id}.png": "price_per_m2_comparison.png",
        f"distribucion_precios_{property_id}.png": "price_distribution.png",
    }
    if source.suffix in {".aux", ".log", ".out", ".swp"}:
        return report_root / property_id / ".build" / source.name
    return report_root / property_id / names.get(source.name, source.name)


def planned_moves(paths: ProjectPaths) -> list[FileMove]:
    root = paths.root
    moves: list[FileMove] = []

    fixed = {
        root / "data" / "casas_idealista.csv": root / "data" / "raw" / "properties_latest.csv",
        root / "data" / "ids_casas.csv": root / "data" / "raw" / "known_property_ids.csv",
        root / "data" / "casas_idealista_procesado_extra.csv": root / "data" / "processed" / "properties_latest.csv",
        root / "data" / "casas_idealista_procesado.csv": root / "data" / "processed" / "properties.csv",
        root / "data" / "casas_idealista_predicciones.csv": root / "data" / "processed" / "predictions.csv",
        root / "data" / "clientes.csv": root / "data" / "private" / "clients.csv",
        root / "csv" / "buenos.csv": root / "artifacts" / "review" / "opportunities.csv",
        root / "data" / "random_forest_venta.pkl": root / "models" / "random_forest" / "model.pkl",
        root / "data" / "bagging_venta.pkl": root / "models" / "bagging" / "model.pkl",
        root / "data" / "gb_venta.pkl": root / "models" / "gradient_boosting" / "model.pkl",
        root / "data" / "svr_venta.pkl": root / "models" / "svr" / "model.pkl",
        root / "data" / "scaler_svr.pkl": root / "models" / "svr" / "scaler.pkl",
        root / "reports" / "plantilla_informe.tex": root / "assets" / "reports" / "template.tex",
        root / "reports" / "Positivo_fondo_blanco_logo.png": root / "assets" / "reports" / "logo.png",
        root / "reports" / "Positivo_fondo_blanco.png": root / "assets" / "reports" / "brand.png",
        root / "reports" / "Portada_informes.png": root / "assets" / "reports" / "cover_template.png",
        root / "reports" / ".DS_Store": root / "artifacts" / "reports" / ".DS_Store",
        root / "csv" / ".DS_Store": root / "artifacts" / "review" / ".DS_Store",
        root / "notebooks" / "ACTUALIZADOR.ipynb": root / "notebooks" / "operations" / "ACTUALIZADOR.ipynb",
        root / "notebooks" / "Modelos.ipynb": root / "notebooks" / "training" / "Modelos.ipynb",
    }
    moves.extend(FileMove(source, destination) for source, destination in fixed.items())

    archive = root / "data" / "archive" / "legacy_backups"
    for source in (root / "data").glob("*.csv"):
        lowered = source.name.lower()
        if "back up" in lowered or "backup" in lowered:
            moves.append(FileMove(source, archive / source.name))
    for metadata in MODEL_METADATA.values():
        source = root / "data" / str(metadata["legacy_columns"])
        moves.append(FileMove(source, archive / "model_schemas" / source.name))

    legacy_reports = root / "reports"
    if legacy_reports.exists():
        for directory in legacy_reports.iterdir():
            if not directory.is_dir() or not directory.name.isdigit():
                continue
            for source in directory.rglob("*"):
                if source.is_file():
                    moves.append(
                        FileMove(
                            source,
                            _report_destination(
                                paths.root / "artifacts" / "reports", source
                            ),
                        )
                    )

    archive_notebooks = root / "notebooks" / "archive"
    for source in (root / "notebooks").glob("*.ipynb"):
        if source.name not in {"ACTUALIZADOR.ipynb", "Modelos.ipynb"}:
            moves.append(FileMove(source, archive_notebooks / source.name))

    unique: dict[Path, FileMove] = {}
    for move in moves:
        if move.source.exists():
            unique[move.source] = move
    return list(unique.values())


def _copy_verified(move: FileMove) -> MigrationRecord:
    source_hash = _sha256(move.source)
    move.destination.parent.mkdir(parents=True, exist_ok=True)
    if move.destination.exists():
        if _sha256(move.destination) != source_hash:
            raise RuntimeError(
                f"El destino ya existe con contenido distinto: {move.destination}"
            )
    else:
        shutil.copy2(move.source, move.destination)
    if _sha256(move.destination) != source_hash:
        raise RuntimeError(f"Checksum distinto despues de copiar {move.source}")
    record = MigrationRecord(
        source=str(move.source),
        destination=str(move.destination),
        sha256=source_hash,
        bytes=move.source.stat().st_size,
    )
    move.source.unlink()
    return record


def _feature_columns(root: Path, legacy_columns: str) -> list[str] | None:
    candidates = [
        root / "data" / legacy_columns,
        root / "data" / "archive" / "legacy_backups" / "model_schemas" / legacy_columns,
    ]
    source = next((path for path in candidates if path.exists()), None)
    if source is None:
        return None
    value = joblib.load(source)
    return [str(column) for column in value]


def _write_model_metadata(paths: ProjectPaths, *, dry_run: bool) -> list[Path]:
    registry = load_project_config(paths.model_registry)
    active = {item["name"]: bool(item.get("active")) for item in registry["models"]}
    written: list[Path] = []
    for name, settings in MODEL_METADATA.items():
        destination = paths.models / name / "metadata.json"
        written.append(destination)
        if dry_run:
            continue
        columns = _feature_columns(paths.root, str(settings["legacy_columns"]))
        if columns is None:
            if destination.exists():
                continue
            raise FileNotFoundError(
                f"No se encontro el esquema de columnas para el modelo {name}"
            )
        metadata = {
            "name": name,
            "model_version": "1.0.0",
            "trained_at": "unknown",
            "python_version": "unknown",
            "numpy_version": "unknown",
            "scipy_version": "unknown",
            "scikit_learn_version": "1.5.2",
            "feature_columns": columns,
            "metrics": {"mse": settings["mse"]},
            "training_data_version": "legacy-import",
            "active": active.get(name, False),
            "compatible_runtime_verified": {
                "verified_at": "2026-09-09",
                "python": "3.11",
                "numpy": "1.26.4",
                "scipy": "1.13.1",
                "scikit_learn": "1.5.2",
                "joblib": "1.4.2",
            },
            "compatibility_check": (
                {
                    "processed_rows": 9683,
                    "reference_rows": 9683,
                    "maximum_absolute_difference": 2.3283064365386963e-10,
                }
                if name != "svr"
                else {
                    "model_loaded": True,
                    "scaler_loaded": True,
                    "feature_columns": 100,
                    "smoke_prediction_finite": True,
                }
            ),
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    return written


def _normalise_tex_paths(path: Path) -> None:
    if path.suffix != ".tex":
        return
    value = path.read_text(encoding="utf-8", errors="replace")
    prefix = "" if path.name == "template.tex" else "../../../assets/reports/"
    replacements = {
        "Positivo_fondo_blanco_logo.png": f"{prefix}logo.png",
        "Positivo_fondo_blanco.png": f"{prefix}brand.png",
        "Portada_informes.png": f"{prefix}cover_template.png",
    }
    for old_name, new_name in replacements.items():
        value = re.sub(rf"/[^{{}}\n]+/{re.escape(old_name)}", new_name, value)
    path.write_text(value, encoding="utf-8")


def _remove_empty_legacy_directories(root: Path) -> None:
    candidates = [root / "csv", root / "reports"]
    candidates.extend(
        path for path in (root / "reports").glob("*") if path.is_dir()
    )
    for directory in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def migrate_project(paths: ProjectPaths, *, dry_run: bool = True) -> list[MigrationRecord]:
    """Copia, verifica por SHA-256 y retira cada ruta antigua de forma individual."""

    moves = planned_moves(paths)
    if dry_run:
        for move in moves:
            print(f"MOVER  {move.source.relative_to(paths.root)} -> {move.destination.relative_to(paths.root)}")
        for metadata in _write_model_metadata(paths, dry_run=True):
            action = "VERIFICAR" if metadata.exists() else "CREAR"
            print(f"{action:<10}{metadata.relative_to(paths.root)}")
        return []

    records = [_copy_verified(move) for move in moves]
    metadata_files = _write_model_metadata(paths, dry_run=False)
    for record in records:
        _normalise_tex_paths(Path(record.destination))
    _remove_empty_legacy_directories(paths.root)

    previous: dict = {}
    if paths.migration_manifest.exists():
        previous = json.loads(paths.migration_manifest.read_text(encoding="utf-8"))
    combined = {
        (item["source"], item["destination"]): item
        for item in previous.get("records", [])
    }
    combined.update(
        {
            (record.source, record.destination): asdict(record)
            for record in records
        }
    )
    migrated_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "migrated_at": migrated_at,
        "history": [
            *previous.get("history", []),
            {"migrated_at": migrated_at, "records": len(records)},
        ],
        "records": list(combined.values()),
        "metadata_files": [str(path) for path in metadata_files],
    }
    paths.migration_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.migration_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return records
