"""Orquestacion explicita de las etapas y persistencia entre ejecuciones."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from .config import AppConfig, ProjectPaths
from .domain.properties import validate_raw
from .matching import read_review, run_matching, selected_properties
from .notifications import send_notifications
from .prediction import run_prediction
from .preprocessing import run_preprocessing
from .reporting import generate_reports, prepare_report_assets
from .sources.base import PropertySource
from .storage import RunState, read_csv_flexible, write_csv_atomic


@dataclass(frozen=True)
class PipelineResult:
    status: str
    new_properties: int = 0
    opportunities: int = 0
    reports: int = 0
    emails: int = 0


def _normalise_ids(values: Iterable[int] | None) -> list[int]:
    if values is None:
        return []
    return list(dict.fromkeys(int(value) for value in values))


def collect_new_properties(paths: ProjectPaths, source: PropertySource) -> list[int]:
    """Persiste el resultado de cualquier fuente sin conocer su tecnologia."""

    known = set()
    if paths.ids.exists():
        known_frame = read_csv_flexible(paths.ids)
        if "id" in known_frame:
            known = set(pd.to_numeric(known_frame["id"], errors="coerce").dropna().astype(int))

    properties = source.collect_new(known)
    if not properties:
        return []
    batch = pd.DataFrame(item.as_record() for item in properties)
    batch = batch.drop_duplicates(subset="id", keep="last").reset_index(drop=True)
    validate_raw(batch)
    write_csv_atomic(batch, paths.raw_properties, encoding="utf-16")

    new_ids = batch["id"].astype(int).tolist()
    combined = pd.DataFrame({"id": sorted(known.union(new_ids))})
    write_csv_atomic(combined, paths.ids)
    return new_ids


def run_core(
    config: AppConfig,
    *,
    source: PropertySource | None = None,
    new_ids: Iterable[int] | None = None,
    auto_approve: bool = False,
    compile_pdf: bool = True,
    send: bool = False,
    prepare_assets: bool = True,
) -> PipelineResult:
    """Ejecuta captacion -> datos -> modelos -> seleccion.

    Sin ``auto_approve`` termina tras generar el CSV de revision. De ese modo
    una ejecucion automatica nunca envia correos sin una decision explicita.
    """

    state = RunState.load(config.paths.run_state)
    ids = _normalise_ids(new_ids)
    if source is not None:
        state = RunState(source=source.name)
        ids = collect_new_properties(config.paths, source)
    elif not ids:
        ids = state.new_ids

    state.new_ids = ids
    state.stats["new_properties"] = len(ids)
    if not ids:
        state.status = "no_new_properties"
        state.save(config.paths.run_state)
        return PipelineResult(status=state.status)

    run_preprocessing(config.paths)
    run_prediction(config.paths)
    review = run_matching(config.paths, ids)
    state.stats["opportunities"] = len(review)
    state.status = "awaiting_review"
    state.save(config.paths.run_state)

    if review.empty:
        state.status = "no_opportunities"
        state.save(config.paths.run_state)
        return PipelineResult(
            status=state.status, new_properties=len(ids), opportunities=0
        )

    if not auto_approve:
        return PipelineResult(
            status=state.status,
            new_properties=len(ids),
            opportunities=len(review),
        )

    review["Seleccionado"] = True
    write_csv_atomic(review, config.paths.review)
    return resume_pipeline(
        config,
        compile_pdf=compile_pdf,
        send=send,
        prepare_assets=prepare_assets,
    )


def resume_pipeline(
    config: AppConfig,
    *,
    compile_pdf: bool = True,
    send: bool = False,
    prepare_assets: bool = True,
) -> PipelineResult:
    state = RunState.load(config.paths.run_state)
    selected = selected_properties(read_review(config.paths.review))
    opportunities = len(selected)
    if prepare_assets and opportunities:
        prepare_report_assets(config)
    reports = generate_reports(config.paths, compile_pdf=compile_pdf)
    state.generated_reports = [str(path) for path in reports]
    state.stats["reports"] = len(reports)
    state.status = "reports_generated"
    state.save(config.paths.run_state)

    emails = send_notifications(config) if send else 0
    if send:
        # El envio persiste claves de idempotencia; se recarga el estado para
        # no sobrescribirlas con la instancia anterior al SMTP.
        state = RunState.load(config.paths.run_state)
        state.stats["emails"] = emails
        state.status = "completed"
        state.save(config.paths.run_state)
    return PipelineResult(
        status=state.status,
        new_properties=len(state.new_ids),
        opportunities=opportunities,
        reports=len(reports),
        emails=emails,
    )
