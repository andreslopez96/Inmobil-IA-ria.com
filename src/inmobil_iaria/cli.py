"""Interfaz unica para operar el proyecto."""

from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from pathlib import Path

from .config import AppConfig, PROJECT_ROOT
from .matching import run_matching
from .migration import migrate_project
from .notifications import notification_preview, send_notifications
from .workflow import PipelineResult, collect_new_properties, resume_pipeline, run_core
from .prediction import model_specs, run_prediction
from .preprocessing import run_preprocessing
from .reporting import generate_reports, prepare_report_assets
from .review import file_version, open_review, wait_until_saved
from .sources.idealista_browser import browser_source_from_config
from .sources.idealista_browser import detect_chrome_major
from .storage import RunState


def _ids(value: str) -> list[int]:
    try:
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as error:
        raise argparse.ArgumentTypeError("Los IDs deben ser numeros separados por comas") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inmobil-iaria",
        description="Pipeline unificado de Inmobil-IA-ria",
    )
    parser.add_argument(
        "--root", type=Path, default=PROJECT_ROOT, help=argparse.SUPPRESS
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Ejecutar hasta preparar la revision")
    run.add_argument("--skip-scrape", action="store_true")
    run.add_argument("--ids", type=_ids, default=[])
    run.add_argument("--auto-approve", action="store_true")
    run.add_argument(
        "--pause-after-review",
        action="store_true",
        help="Abrir el CSV y terminar; continuar mas tarde con resume",
    )
    run.add_argument(
        "--no-open-review",
        action="store_true",
        help="No abrir automaticamente el CSV de revision",
    )
    run.add_argument("--no-pdf", action="store_true")
    run.add_argument(
        "--send",
        action="store_true",
        help="Enviar correos; requiere tambien --auto-approve",
    )

    commands.add_parser("scrape", help="Captar anuncios nuevos")
    commands.add_parser("process", help="Transformar y consolidar datos")
    commands.add_parser("predict", help="Ejecutar los modelos")
    match = commands.add_parser("match", help="Cruzar oportunidades y clientes")
    match.add_argument("--ids", type=_ids, default=[])
    match.add_argument("--no-open-review", action="store_true")
    reports = commands.add_parser("reports", help="Crear informes seleccionados")
    reports.add_argument("--no-pdf", action="store_true")
    resume = commands.add_parser("resume", help="Continuar despues de la revision")
    resume.add_argument("--no-pdf", action="store_true")
    resume.add_argument("--send", action="store_true")
    notify = commands.add_parser("notify", help="Previsualizar o enviar correos")
    notify.add_argument("--send", action="store_true")
    commands.add_parser("doctor", help="Comprobar archivos y dependencias")
    migrate = commands.add_parser("migrate", help="Reorganizar rutas con checksums")
    migrate.add_argument(
        "--apply",
        action="store_true",
        help="Aplicar los movimientos; sin esta opcion solo muestra el plan",
    )
    return parser


def _show_result(result: PipelineResult, review_path: Path) -> None:
    print(
        f"Estado: {result.status} | nuevos: {result.new_properties} | "
        f"oportunidades: {result.opportunities} | informes: {result.reports} | "
        f"correos: {result.emails}"
    )
    if result.status == "awaiting_review":
        print(f"Revisa {review_path}, marca Seleccionado y ejecuta: immobil-iaria resume")


def _doctor(config: AppConfig) -> int:
    checks: list[tuple[str, bool, str]] = []
    for label, path in {
        "datos sin procesar": config.paths.raw_properties,
        "datos procesados": config.paths.processed_properties,
        "clientes": config.paths.clients,
        "plantilla": config.paths.report_template,
    }.items():
        checks.append((label, path.exists(), str(path)))
    for spec in model_specs(config.paths):
        checks.append(
            (
                spec.output,
                spec.model.exists() and spec.metadata.exists(),
                str(spec.model),
            )
        )
    for package in (
        "pandas",
        "sklearn",
        "joblib",
        "bs4",
        "selenium",
        "undetected_chromedriver",
    ):
        try:
            importlib.import_module(package)
        except Exception as error:
            checks.append((f"Python: {package}", False, f"{type(error).__name__}: {error}"))
        else:
            checks.append((f"Python: {package}", True, package))
    checks.append(("pdflatex", shutil.which("pdflatex") is not None, "PATH"))
    chrome_major = detect_chrome_major()
    checks.append(
        (
            "Google Chrome",
            chrome_major is not None,
            f"version principal {chrome_major}" if chrome_major else "no detectado",
        )
    )

    for label, ok, detail in checks:
        print(f"{'OK' if ok else 'FALTA':5}  {label}: {detail}")
    return 0 if all(ok for _, ok, _ in checks) else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    config = AppConfig.from_env(args.root)

    try:
        if args.command == "run":
            if args.send and args.pause_after_review and not args.auto_approve:
                raise ValueError(
                    "--send no puede usarse con --pause-after-review; "
                    "envia despues con resume --send"
                )
            result = run_core(
                config,
                source=(
                    None
                    if args.skip_scrape
                    else browser_source_from_config(config, progress=print)
                ),
                new_ids=args.ids,
                auto_approve=args.auto_approve,
                compile_pdf=not args.no_pdf,
                send=args.send,
            )
            _show_result(result, config.paths.review)
            if result.status == "awaiting_review":
                version = file_version(config.paths.review)
                if not args.no_open_review:
                    open_review(config.paths.review)
                    print(f"CSV abierto: {config.paths.review}")
                if not args.pause_after_review:
                    print(
                        "Marca Seleccionado como Sí en los inmuebles deseados "
                        "y guarda el CSV. Esperando cambios..."
                    )
                    wait_until_saved(config.paths.review, version)
                    result = resume_pipeline(
                        config, compile_pdf=not args.no_pdf, send=args.send
                    )
                    _show_result(result, config.paths.review)
        elif args.command == "scrape":
            source = browser_source_from_config(config, progress=print)
            ids = collect_new_properties(config.paths, source)
            state = RunState(new_ids=ids, status="collected", source=source.name)
            state.save(config.paths.run_state)
            print(f"Inmuebles nuevos: {len(ids)}")
        elif args.command == "process":
            print(f"Registros procesados: {len(run_preprocessing(config.paths))}")
        elif args.command == "predict":
            print(f"Predicciones: {len(run_prediction(config.paths))}")
        elif args.command == "match":
            state = RunState.load(config.paths.run_state)
            ids = args.ids or state.new_ids
            review = run_matching(config.paths, ids)
            print(f"Oportunidades para revisar: {len(review)} en {config.paths.review}")
            if not review.empty and not args.no_open_review:
                open_review(config.paths.review)
        elif args.command == "reports":
            prepare_report_assets(config, progress=print)
            generated = generate_reports(config.paths, compile_pdf=not args.no_pdf)
            print(f"Informes generados: {len(generated)}")
        elif args.command == "resume":
            _show_result(
                resume_pipeline(
                    config, compile_pdf=not args.no_pdf, send=args.send
                ),
                config.paths.review,
            )
        elif args.command == "notify":
            if args.send:
                print(f"Correos enviados: {send_notifications(config)}")
            else:
                preview = notification_preview(config)
                print(f"Previsualizacion: {len(preview)} clientes recibirian informes")
                for client_id, reports in preview.items():
                    print(f"  cliente {client_id}: {len(reports)} informe(s)")
        elif args.command == "doctor":
            return _doctor(config)
        elif args.command == "migrate":
            records = migrate_project(config.paths, dry_run=not args.apply)
            if args.apply:
                print(f"Migracion completada: {len(records)} archivos verificados")
            else:
                print("Vista previa terminada; usa migrate --apply para ejecutar")
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
