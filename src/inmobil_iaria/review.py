"""Apertura y espera de la revision humana de oportunidades."""

from __future__ import annotations

import os
import platform
import subprocess
import time
from pathlib import Path


def file_version(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def open_review(path: Path) -> None:
    """Abre el CSV con la aplicacion predeterminada del sistema."""

    system = platform.system()
    if system == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
        return

    command = "open" if system == "Darwin" else "xdg-open"
    try:
        subprocess.Popen(
            [command, str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            f"No se pudo abrir {path}; abre el archivo manualmente"
        ) from error


def wait_until_saved(
    path: Path,
    initial_version: tuple[int, int],
    *,
    poll_seconds: float = 1.0,
) -> None:
    """Espera un guardado completo, no solo el primer evento de escritura."""

    while file_version(path) == initial_version:
        time.sleep(poll_seconds)

    # Algunas aplicaciones reemplazan el CSV mediante varias escrituras. Se
    # continúa cuando tamaño y fecha permanecen estables durante dos sondeos.
    stable_version = file_version(path)
    stable_polls = 0
    while stable_polls < 2:
        time.sleep(poll_seconds)
        current = file_version(path)
        if current == stable_version:
            stable_polls += 1
        else:
            stable_version = current
            stable_polls = 0

