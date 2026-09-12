"""Configuracion central y rutas portables del proyecto."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependencia opcional durante diagnostico
    load_dotenv = None


def _discover_project_root() -> Path:
    explicit = os.getenv("INMOBIL_PROJECT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()
    current = Path.cwd().resolve()
    candidates = (current, *current.parents, *Path(__file__).resolve().parents)
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists() and (
            candidate / "config"
        ).exists():
            return candidate
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _discover_project_root()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def load_project_config(path: Path) -> dict[str, Any]:
    """Lee configuracion JSON-compatible YAML sin añadir otra dependencia.

    Los ficheros ``config/*.yaml`` usan sintaxis JSON, que es un subconjunto
    valido de YAML. Esto mantiene el despliegue pequeño y la lectura estricta.
    """

    if not path.exists():
        raise FileNotFoundError(f"No existe la configuracion requerida: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Configuracion no valida en {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"La configuracion debe ser un objeto: {path}")
    return value


@dataclass(frozen=True)
class ProjectPaths:
    """Ubicaciones nuevas con compatibilidad de lectura para el arbol antiguo."""

    root: Path = PROJECT_ROOT

    def _preferred(self, preferred: Path, legacy: Path | None = None) -> Path:
        if preferred.exists() or legacy is None or not legacy.exists():
            return preferred
        return legacy

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def raw_data(self) -> Path:
        return self.data / "raw"

    @property
    def processed_data(self) -> Path:
        return self.data / "processed"

    @property
    def private_data(self) -> Path:
        return self.data / "private"

    @property
    def reference_data(self) -> Path:
        return self.data / "reference"

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def assets(self) -> Path:
        return self.root / "assets" / "reports"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def reports(self) -> Path:
        return self._preferred(self.artifacts / "reports", self.root / "reports")

    @property
    def review(self) -> Path:
        return self._preferred(
            self.artifacts / "review" / "opportunities.csv",
            self.root / "csv" / "buenos.csv",
        )

    @property
    def run_state(self) -> Path:
        return self.root / ".runtime" / "latest_run.json"

    @property
    def migration_manifest(self) -> Path:
        return self.root / ".runtime" / "migration_manifest.json"

    @property
    def ids(self) -> Path:
        return self._preferred(
            self.raw_data / "known_property_ids.csv", self.data / "ids_casas.csv"
        )

    @property
    def raw_properties(self) -> Path:
        return self._preferred(
            self.raw_data / "properties_latest.csv",
            self.data / "casas_idealista.csv",
        )

    @property
    def processed_batch(self) -> Path:
        return self._preferred(
            self.processed_data / "properties_latest.csv",
            self.data / "casas_idealista_procesado_extra.csv",
        )

    @property
    def processed_properties(self) -> Path:
        return self._preferred(
            self.processed_data / "properties.csv",
            self.data / "casas_idealista_procesado.csv",
        )

    @property
    def predictions(self) -> Path:
        return self._preferred(
            self.processed_data / "predictions.csv",
            self.data / "casas_idealista_predicciones.csv",
        )

    @property
    def clients(self) -> Path:
        return self._preferred(
            self.private_data / "clients.csv", self.data / "clientes.csv"
        )

    @property
    def clients_example(self) -> Path:
        return self.reference_data / "clients.example.csv"

    @property
    def report_template(self) -> Path:
        return self._preferred(
            self.assets / "template.tex", self.root / "reports" / "plantilla_informe.tex"
        )

    @property
    def model_registry(self) -> Path:
        return self.root / "config" / "model_registry.yaml"

    @property
    def matching_rules(self) -> Path:
        return self.root / "config" / "matching_rules.yaml"

    def model_file(self, name: str) -> Path:
        """Resuelve nombres historicos hacia el registro nuevo de modelos."""

        locations = {
            "random_forest_venta.pkl": self.models / "random_forest" / "model.pkl",
            "bagging_venta.pkl": self.models / "bagging" / "model.pkl",
            "gb_venta.pkl": self.models / "gradient_boosting" / "model.pkl",
            "svr_venta.pkl": self.models / "svr" / "model.pkl",
            "scaler_svr.pkl": self.models / "svr" / "scaler.pkl",
        }
        preferred = locations.get(name, self.models / name)
        return self._preferred(preferred, self.data / name)

    def model_metadata(self, directory: str, legacy_columns: str) -> Path:
        return self._preferred(
            self.models / directory / "metadata.json", self.data / legacy_columns
        )


@dataclass(frozen=True)
class AppConfig:
    paths: ProjectPaths
    smtp_host: str
    smtp_port: int
    smtp_ssl: bool
    email_sender: str | None
    email_password: str | None
    headless: bool
    known_id_repeat_limit: int
    idealista_api_key: str | None
    idealista_api_secret: str | None

    @classmethod
    def from_env(cls, root: Path | None = None) -> "AppConfig":
        project_root = (root or PROJECT_ROOT).resolve()
        if load_dotenv is not None:
            load_dotenv(project_root / ".env")

        return cls(
            paths=ProjectPaths(project_root),
            smtp_host=os.getenv("INMOBIL_SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("INMOBIL_SMTP_PORT", "587")),
            smtp_ssl=_as_bool(os.getenv("INMOBIL_SMTP_SSL"), default=False),
            email_sender=os.getenv("INMOBIL_EMAIL_SENDER") or None,
            email_password=os.getenv("INMOBIL_EMAIL_PASSWORD") or None,
            headless=_as_bool(os.getenv("INMOBIL_HEADLESS"), default=False),
            known_id_repeat_limit=max(
                1, int(os.getenv("INMOBIL_KNOWN_ID_REPEAT_LIMIT", "5"))
            ),
            idealista_api_key=os.getenv("INMOBIL_IDEALISTA_API_KEY") or None,
            idealista_api_secret=os.getenv("INMOBIL_IDEALISTA_API_SECRET") or None,
        )

    def require_email(self) -> None:
        missing = []
        if not self.email_sender:
            missing.append("INMOBIL_EMAIL_SENDER")
        if not self.email_password:
            missing.append("INMOBIL_EMAIL_PASSWORD")
        if missing:
            raise RuntimeError(
                "Falta configurar el correo en .env: " + ", ".join(missing)
            )
