#!/usr/bin/env python3
"""Gmail transport for the GitHub-hosted catalog updater."""

from __future__ import annotations

import argparse
import base64
import email.message
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".github" / "catalog-automation-state.json"
REPORT = ROOT / "inventory_update_report.json"
SCOPES = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send"


def request_json(url: str, token: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def access_token() -> str:
    values = {
        "client_id": os.environ["GMAIL_CLIENT_ID"],
        "client_secret": os.environ["GMAIL_CLIENT_SECRET"],
        "refresh_token": os.environ["GMAIL_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
        "scope": SCOPES,
    }
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode(values).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)["access_token"]
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "Gmail OAuth refresh failed. Re-run scripts/authorize_gmail.py to "
            "refresh the GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and "
            f"GMAIL_REFRESH_TOKEN GitHub secrets. Google response: {detail}"
        ) from error


def walk_parts(part: dict):
    yield part
    for child in part.get("parts", []):
        yield from walk_parts(child)


def newest_workbook(token: str) -> tuple[bytes, str, str]:
    query = 'has:attachment filename:xlsx from:(oliver_rodry@icloud.com)'
    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?" + urllib.parse.urlencode({"q": query, "maxResults": 20})
    listing = request_json(url, token)
    for item in listing.get("messages", []):
        workbook = message_workbook(token, item["id"])
        if workbook is not None:
            return workbook
    raise RuntimeError("No forwarded Gmail message with an .xlsx attachment was found.")


def message_workbook(token: str, message_id: str) -> tuple[bytes, str, str] | None:
    message = request_json(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}?format=full", token)
    for part in walk_parts(message.get("payload", {})):
        filename = part.get("filename", "")
        attachment_id = part.get("body", {}).get("attachmentId")
        if filename.lower().endswith(".xlsx") and attachment_id:
            attachment = request_json(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/attachments/{attachment_id}", token
            )
            return base64.urlsafe_b64decode(attachment["data"] + "==="), filename, message_id
    return None


def output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def prepare() -> int:
    token = access_token()
    previous_state = json.loads(STATE.read_text()) if STATE.exists() else {}
    pending = previous_state.get("report_pending", False)
    if pending:
        result = message_workbook(token, previous_state["gmail_message_id"])
        if result is None:
            raise RuntimeError("Pending inventory attachment is missing; keeping the original baseline for recovery.")
        workbook, filename, message_id = result
    else:
        workbook, filename, message_id = newest_workbook(token)
    digest = hashlib.sha256(workbook).hexdigest()
    if not pending and previous_state.get("gmail_message_id") == message_id:
        output("duplicate", "true")
        print("Latest Gmail message was already processed.")
        return 0
    if pending and digest != previous_state["last_workbook_sha256"]:
        raise RuntimeError("Pending inventory attachment does not match its saved checksum.")
    base_commit = previous_state["report_base_commit"] if pending else subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    base_state = previous_state["report_previous_state"] if pending else {
        key: previous_state.get(key, "No registrado") for key in ("workbook_filename", "processed_at")
    }
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as source, tempfile.NamedTemporaryFile(suffix=".csv") as baseline:
        source.write(workbook)
        source.flush()
        baseline.write(subprocess.check_output(["git", "show", f"{base_commit}:products.csv"], cwd=ROOT))
        baseline.flush()
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "update_catalog.py"),
                "--input", source.name,
                "--baseline", baseline.name,
                "--output", str(ROOT / "products.csv"),
                "--overrides", str(ROOT / "inventory_overrides.json"),
                "--report", str(REPORT),
                "--apply",
            ],
            cwd=ROOT,
            check=True,
        )
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["workbook"] = filename
    report["previous_workbook"] = base_state["workbook_filename"]
    report["previous_update_at"] = base_state["processed_at"]
    report["gmail_message_id"] = message_id
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state = {
        "last_workbook_sha256": digest,
        "processed_at": previous_state["processed_at"] if pending else datetime.now(timezone.utc).isoformat(),
        "gmail_message_id": message_id,
        "workbook_filename": filename,
        "report_pending": True,
        "report_base_commit": base_commit,
        "report_previous_state": base_state,
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    output("duplicate", "false")
    return 0


def report_body(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "El catálogo fue actualizado correctamente.",
        "",
        f"Inventario anterior: {report.get('previous_workbook', 'No registrado')}",
        f"Última actualización anterior (UTC): {report.get('previous_update_at', 'No registrado')}",
        f"Inventario actual: {report.get('workbook', 'No registrado')}",
        f"Reporte generado (UTC): {report.get('generated_at', 'No registrado')}",
        "Comparación acumulada entre estos inventarios; no corresponde únicamente a ventas de hoy.",
        "",
        f"Unidades vendidas (incluyendo servicios): {summary['sold_units_including_services']}",
        f"Venta estimada: RD${DecimalFormat(summary['estimated_sales_dop_including_services'])}",
        "",
        "Detalle de ventas:",
    ]
    if report["sold"]:
        for item in report["sold"]:
            lines.append(
                f"- {item['name']}: {item['units']} × RD${DecimalFormat(item['unit_price_dop'])} = RD${DecimalFormat(item['estimated_dop'])}"
            )
    else:
        lines.append("- No se detectaron disminuciones de inventario.")
    lines.extend(["", "Artículos nuevos agotados:"])
    if report["newly_out_of_stock"]:
        lines.extend(f"- {item['name']} (SKU: {item['sku']})" for item in report["newly_out_of_stock"])
    else:
        lines.append("- No hay artículos nuevos agotados.")
    lines.extend(["", "Cambios de precio:"])
    if report["price_changes"]:
        lines.extend(
            f"- {item['name']}: RD${DecimalFormat(item['old_price'])} → RD${DecimalFormat(item['new_price'])}"
            for item in report["price_changes"]
        )
    else:
        lines.append("- Sin cambios de precio.")
    lines.extend(["", "Reposiciones:"])
    if report["restocked"]:
        lines.extend(f"- {item['name']}: +{item['units_added']}" for item in report["restocked"])
    else:
        lines.append("- Sin reposiciones.")
    for key, title in (("new_products", "Productos nuevos"), ("removed_products", "Productos retirados")):
        lines.extend(["", f"{title}:"])
        items = report.get(key, [])
        lines.extend(f"- {item['name']} (SKU: {item['sku']})" for item in items)
        if not items:
            lines.append("- Ninguno.")
    lines.extend(
        [
            "",
            "Nota: la venta es una estimación basada en disminuciones de inventario multiplicadas por el precio anterior. Puede diferir del efectivo recibido si hubo ajustes de inventario.",
        ]
    )
    return "\n".join(lines)


def DecimalFormat(value: object) -> str:  # noqa: N802
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def send() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if not state.get("report_pending"):
        print("Report is already marked as sent.")
        return 0
    if report.get("gmail_message_id") != state["gmail_message_id"]:
        raise RuntimeError("Report does not belong to the pending inventory.")
    token = access_token()
    # Search Sent before retrying: the send may have succeeded before a runner or push failed.
    message_id = f"catalog-inventory-{state['gmail_message_id']}@papeleriasolnaciente.com"
    query = urllib.parse.urlencode({"q": f"in:sent rfc822msgid:{message_id}", "maxResults": 1})
    sent = request_json(f"https://gmail.googleapis.com/gmail/v1/users/me/messages?{query}", token)
    if sent.get("messages"):
        state["report_pending"] = False
        STATE.write_text(json.dumps(state, indent=2) + "\n")
        print("Existing sent report found; skipping duplicate delivery.")
        return 0
    message = email.message.EmailMessage()
    message["Message-ID"] = f"<{message_id}>"
    message["To"] = "oliver_rodry@icloud.com"
    message["Subject"] = "Catálogo actualizado - comparación con la última actualización"
    message.set_content(report_body(report))
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
    request_json(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        token,
        method="POST",
        body={"raw": raw},
    )
    state["report_pending"] = False
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    print("Confirmation email sent to oliver_rodry@icloud.com.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "send"])
    args = parser.parse_args()
    return prepare() if args.command == "prepare" else send()


if __name__ == "__main__":
    raise SystemExit(main())
