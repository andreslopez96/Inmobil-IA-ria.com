"""Distribucion de informes por cliente."""

from __future__ import annotations

import smtplib
from collections import defaultdict
from email.message import EmailMessage
from pathlib import Path

import pandas as pd

from .config import AppConfig
from .matching import parse_interested_clients, read_review, selected_properties
from .storage import RunState, read_csv


def reports_by_client(
    selected: pd.DataFrame, report_paths: list[Path]
) -> dict[str, list[Path]]:
    by_property = {
        (
            int(path.parent.name)
            if path.name == "report.pdf"
            else int(path.stem.removeprefix("informe_"))
        ): path
        for path in report_paths
    }
    grouped: dict[str, list[Path]] = defaultdict(list)
    for _, property_row in selected.iterrows():
        report = by_property.get(int(property_row["id"]))
        if report is None or not report.exists():
            continue
        for client_id in parse_interested_clients(
            property_row["Clientes_Interesados"]
        ):
            grouped[client_id].append(report)
    return dict(grouped)


def _message(sender: str, client: pd.Series, reports: list[Path]) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = (
        "Informes inmobiliarios recientes - Oportunidades destacadas para ti"
    )
    message["From"] = sender
    message["To"] = str(client["email"])
    message.set_content(
        f"Estimado/a {client.get('nombre', '')},\n\n"
        "Te adjuntamos los informes más recientes que cumplen tus preferencias "
        "de inversión.\n\nUn cordial saludo,\nEl equipo de Inmobil-IA-ria."
    )
    for report in reports:
        message.add_attachment(
            report.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=report.name,
        )
    return message


def notification_preview(config: AppConfig) -> dict[str, list[Path]]:
    selected = selected_properties(read_review(config.paths.review))
    reports = []
    for _, row in selected.iterrows():
        directory = config.paths.reports / str(int(row["id"]))
        preferred = directory / "report.pdf"
        legacy = directory / f"informe_{int(row['id'])}.pdf"
        reports.append(preferred if preferred.exists() or not legacy.exists() else legacy)
    return reports_by_client(selected, reports)


def send_notifications(config: AppConfig) -> int:
    config.require_email()
    grouped = notification_preview(config)
    if not grouped:
        return 0
    clients = read_csv(config.paths.clients)
    clients["_id"] = clients["id"].astype(str)
    state = RunState.load(config.paths.run_state)
    sent = 0

    smtp_class = smtplib.SMTP_SSL if config.smtp_ssl else smtplib.SMTP
    with smtp_class(config.smtp_host, config.smtp_port) as server:
        if not config.smtp_ssl:
            server.starttls()
        server.login(config.email_sender, config.email_password)
        for client_id, reports in grouped.items():
            keys = [
                f"{client_id}:{report.parent.name}:1.0.0" for report in reports
            ]
            pending = [
                report
                for report, key in zip(reports, keys)
                if key not in state.sent_notifications
            ]
            if not pending:
                continue
            match = clients[clients["_id"] == client_id]
            if match.empty or pd.isna(match.iloc[0].get("email")):
                continue
            # send_message solo retorna despues de que el servidor ha aceptado
            # la operacion; el estado se persiste inmediatamente despues.
            server.send_message(_message(config.email_sender or "", match.iloc[0], pending))
            state.sent_notifications.extend(
                key for key in keys if key not in state.sent_notifications
            )
            state.save(config.paths.run_state)
            sent += 1
    return sent
