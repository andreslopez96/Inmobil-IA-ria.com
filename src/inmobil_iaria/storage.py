"""Lectura y escritura consistente de los artefactos del pipeline."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


CSV_SEPARATOR = ";"


def read_csv(path: Path, *, encoding: str = "utf-8") -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo requerido: {path}")
    return pd.read_csv(path, sep=CSV_SEPARATOR, encoding=encoding)


def read_csv_flexible(path: Path, *, encoding: str = "utf-8") -> pd.DataFrame:
    """Autodetecta `;` o `,` para artefactos editados por aplicaciones externas."""

    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo requerido: {path}")
    # csv.Sniffer (usado por pandas con ``sep=None``) puede interpretar un
    # digito repetido como separador en un CSV valido de una sola columna. El
    # registro de IDs tiene precisamente ese formato, por lo que elegimos el
    # separador a partir de la cabecera en vez de inferirlo desde los datos.
    with path.open("r", encoding=encoding) as stream:
        header = stream.readline()
    separator = next((item for item in (";", ",", "\t") if item in header), ";")
    return pd.read_csv(path, sep=separator, encoding=encoding)


def write_csv_atomic(
    dataframe: pd.DataFrame,
    path: Path,
    *,
    encoding: str = "utf-8",
) -> None:
    """Evita dejar un CSV incompleto si una ejecucion se interrumpe."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        dataframe.to_csv(
            temporary_path,
            sep=CSV_SEPARATOR,
            index=False,
            encoding=encoding,
        )
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


@dataclass
class RunState:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    new_ids: list[int] = field(default_factory=list)
    generated_reports: list[str] = field(default_factory=list)
    status: str = "created"
    source: str | None = None
    stats: dict[str, int] = field(default_factory=dict)
    sent_notifications: list[str] = field(default_factory=list)
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def load(cls, path: Path) -> "RunState":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            run_id=str(data.get("run_id") or uuid.uuid4().hex),
            new_ids=[int(value) for value in data.get("new_ids", [])],
            generated_reports=list(data.get("generated_reports", [])),
            status=str(data.get("status", "created")),
            source=data.get("source"),
            stats={str(key): int(value) for key, value in data.get("stats", {}).items()},
            sent_notifications=[str(value) for value in data.get("sent_notifications", [])],
            updated_at=str(
                data.get("updated_at") or datetime.now(timezone.utc).isoformat()
            ),
        )

    def save(self, path: Path) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
