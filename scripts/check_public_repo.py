#!/usr/bin/env python3
"""Falla si el arbol publico contiene datos, credenciales o PII evidente."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
}
FORBIDDEN_SUFFIXES = {
    ".csv",
    ".eml",
    ".feather",
    ".joblib",
    ".parquet",
    ".pdf",
    ".pkl",
    ".tsv",
    ".xls",
    ".xlsx",
}
FORBIDDEN_NAMES = {
    ".env",
    ".env.local",
    "credentials.json",
    "service-account.json",
    "token.json",
}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".ini",
    ".ipynb",
    ".json",
    ".lock",
    ".md",
    ".py",
    ".toml",
    ".tex",
    ".txt",
    ".yaml",
    ".yml",
}

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LOCAL_PATH = re.compile(
    re.escape("/" + "Users" + "/")
    + r"|"
    + re.escape("/" + "home" + "/")
    + r"|[A-Z]:\\\\"
    + "Users"
    + r"\\\\",
    re.IGNORECASE,
)
SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?m)^[A-Z][A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY)"
    r"[A-Z0-9_]*\s*=(?!=)\s*[^\s#]+"
)
PRIVATE_KEY = "-----BEGIN " + "PRIVATE KEY-----"
CREDENTIAL_PREFIXES = (
    "sk" + "-",
    "gh" + "p_",
    "gh" + "o_",
    "gh" + "s_",
    "github" + "_pat_",
    "AK" + "IA",
)


def _files() -> list[Path]:
    try:
        git_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        git_root = ""
    if git_root and Path(git_root).resolve() == ROOT:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        return sorted(
            ROOT / name.decode("utf-8")
            for name in listed.split(b"\0")
            if name
        )

    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not IGNORED_DIRS.intersection(path.relative_to(ROOT).parts)
    )


def _allowed_email(value: str) -> bool:
    domain = value.rsplit("@", 1)[-1].lower()
    return domain.endswith(".invalid") or domain in {"example.com", "example.org"}


def main() -> int:
    problems: list[str] = []
    for path in _files():
        relative = path.relative_to(ROOT)
        lower_name = path.name.lower()
        if lower_name in FORBIDDEN_NAMES and lower_name != ".env.example":
            problems.append(f"archivo de entorno o credenciales: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"dato o artefacto prohibido: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2_000_000:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if LOCAL_PATH.search(text):
            problems.append(f"ruta local absoluta: {relative}")
        if SENSITIVE_ASSIGNMENT_PATTERN.search(text) or PRIVATE_KEY in text:
            problems.append(f"secreto con valor aparente: {relative}")
        if any(prefix in text for prefix in CREDENTIAL_PREFIXES):
            problems.append(f"prefijo de credencial conocido: {relative}")
        real_emails = sorted({value for value in EMAIL.findall(text) if not _allowed_email(value)})
        if real_emails:
            problems.append(f"email no ficticio: {relative}")

    if problems:
        print("Control de publicación fallido:", file=sys.stderr)
        for problem in sorted(set(problems)):
            print(f"- {problem}", file=sys.stderr)
        return 1

    print(f"Control de publicación superado: {len(_files())} archivos revisados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
