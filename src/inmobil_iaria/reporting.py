"""Creacion determinista de informes LaTeX y PDF."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pandas as pd

from .config import AppConfig, ProjectPaths
from .matching import read_review, selected_properties
from .storage import write_csv_atomic


def _latex_escape(value: object) -> str:
    text = "No disponible" if pd.isna(value) else str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(character, character) for character in text)


def _integer(info: pd.Series, key: str) -> int | str:
    value = info.get(key)
    return "No disponible" if pd.isna(value) else int(value)


def render_tex(template: str, info: pd.Series, paths: ProjectPaths) -> str:
    price = float(info["Precio"])
    difference = float(info["Diferencia_Ponderada"])
    estimate = round((price + difference) / 10_000) * 10_000
    minimum = max(
        int(10_000 * ((price + difference - 10_000 - 0.66 * difference) // 10_000)),
        int(((price + 9_999) // 10_000) * 10_000),
    )
    maximum = int(
        10_000 * ((price + difference + 10_000 - 0.66 * difference) // 10_000)
    )
    interval = (
        f"\\num{{{minimum}}} €"
        if minimum == maximum
        else f"\\num{{{minimum}}} - \\num{{{maximum}}} €"
    )
    values = {
        "ID": int(info["id"]),
        "TITULO": _latex_escape(
            info.get("Titulo") or f"Inmueble {int(info['id'])}"
        ),
        "LOCALIZACION": _latex_escape(info["Localizacion"]),
        "PRECIO": int(price),
        "M2_CONSTRUIDOS": _integer(info, "m2_construidos"),
        "M2_UTIL": _integer(info, "m2_utiles"),
        "HABITACIONES": _integer(info, "habitaciones"),
        "BANOS": _integer(info, "banos"),
        "ESTADO": _latex_escape(info.get("estado_vivienda", "No disponible")),
        "ASCENSOR": "Sí" if bool(info.get("ascensor", 0)) else "No",
        "CALEFACCION": _latex_escape(info.get("Calefacción", "No disponible")),
        "ANO": _integer(info, "ano_construccion"),
        "ESTIMACION": estimate,
        "MINIMO": minimum,
        "MAXIMO": maximum,
        "INTERVALO": interval,
    }
    result = template
    for key, value in values.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))

    # Los informes se compilan desde artifacts/reports/<id>. Las rutas siguen
    # siendo portables aunque la raiz del repositorio cambie de maquina.
    for old_name, new_name in {
        "Positivo_fondo_blanco_logo.png": "logo.png",
        "Positivo_fondo_blanco.png": "brand.png",
        "Portada_informes.png": "cover_template.png",
    }.items():
        result = re.sub(
            rf"(?<=\{{)[^{{}}\n]*{re.escape(old_name)}(?=\}})",
            f"../../../assets/reports/{new_name}",
            result,
        )
        result = re.sub(
            rf"(?<=\{{)[^{{}}\n]*{re.escape(new_name)}(?=\}})",
            f"../../../assets/reports/{new_name}",
            result,
        )
    return result


def prepare_report_assets(config: AppConfig, *, progress=print) -> pd.DataFrame:
    """Scrapea título y portada después de la aprobación humana."""

    from .sources.idealista_browser import scrape_report_assets

    review = read_review(config.paths.review)
    selected = selected_properties(review)
    if selected.empty:
        return selected
    ids = selected["id"].astype(int).tolist()
    titles = scrape_report_assets(config, ids, progress=progress)
    if titles:
        if "Titulo" not in review:
            review["Titulo"] = ""
        review["Titulo"] = review.apply(
            lambda row: titles.get(int(row["id"]), row.get("Titulo", "")),
            axis=1,
        )
        write_csv_atomic(review, config.paths.review)
    return selected_properties(review)


def _remove_missing_cover(tex: str, report_dir: Path, listing_id: int) -> str:
    if (report_dir / "cover.png").exists():
        return tex.replace(f"Portada_{listing_id}.png", "cover.png")
    if (report_dir / f"Portada_{listing_id}.png").exists():
        return tex
    return re.sub(
        r"\\begin\{tcolorbox\}.*?\\end\{tcolorbox\}",
        "",
        tex,
        count=1,
        flags=re.DOTALL,
    )


def generate_reports(paths: ProjectPaths, *, compile_pdf: bool = True) -> list[Path]:
    review = selected_properties(read_review(paths.review))
    if review.empty:
        return []
    template = paths.report_template.read_text(encoding="utf-8")
    generated: list[Path] = []

    for _, info in review.iterrows():
        listing_id = int(info["id"])
        report_dir = paths.reports / str(listing_id)
        report_dir.mkdir(parents=True, exist_ok=True)
        tex_path = report_dir / "source.tex"
        pdf_path = report_dir / "report.pdf"
        build_dir = report_dir / ".build"
        manifest_path = report_dir / "report.json"
        tex = _remove_missing_cover(
            render_tex(template, info, paths), report_dir, listing_id
        )
        temporary_tex = tex_path.with_suffix(".tmp")
        temporary_tex.write_text(tex, encoding="utf-8")
        temporary_tex.replace(tex_path)
        fingerprint = hashlib.sha256(tex.encode("utf-8")).hexdigest()

        if not compile_pdf:
            generated.append(tex_path)
            continue
        if manifest_path.exists() and pdf_path.exists():
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            if previous.get("source_sha256") == fingerprint:
                generated.append(pdf_path)
                continue
        try:
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", tex_path.name],
                cwd=report_dir,
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError("pdflatex no esta instalado o no esta en PATH") from error
        except subprocess.CalledProcessError as error:
            details = error.stderr.decode(errors="replace") or error.stdout.decode(
                errors="replace"
            )
            raise RuntimeError(f"Fallo compilando {tex_path}:\n{details[-2000:]}") from error
        compiled_pdf = report_dir / "source.pdf"
        if not compiled_pdf.exists():
            raise RuntimeError(f"LaTeX no produjo el PDF esperado: {compiled_pdf}")
        compiled_pdf.replace(pdf_path)
        build_dir.mkdir(exist_ok=True)
        for suffix in (".aux", ".log", ".out"):
            auxiliary = report_dir / f"source{suffix}"
            if auxiliary.exists():
                auxiliary.replace(build_dir / auxiliary.name)
        manifest_path.write_text(
            json.dumps(
                {"property_id": listing_id, "source_sha256": fingerprint}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        generated.append(pdf_path)
    return generated
