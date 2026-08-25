#!/usr/bin/env python3
"""Publish an in-stock catalog product to Facebook and Instagram."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "products.csv"
IMAGE_DIR = ROOT / "img" / "products"
STATE = ROOT / ".github" / "social-posting-state.json"
SITE_URL = "https://papeleriasolnaciente.com"
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
LOCAL_TZ = ZoneInfo("America/Santo_Domingo")
CAMPAIGN_START = date(2026, 8, 24)
CAMPAIGN_END = date(2026, 8, 31)
POSTING_HOURS = (8, 10, 12, 14, 16, 18, 20)
EXTRA_POSTING_HOURS_BY_DATE = {
    date(2026, 8, 24): (22,),
}


class MetaError(RuntimeError):
    pass


def output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def request_json(path: str, token: str, method: str = "GET", values: dict[str, object] | None = None) -> dict:
    data = None
    url = f"{GRAPH_URL}/{path.lstrip('/')}"
    if values:
        encoded = urllib.parse.urlencode({key: str(value) for key, value in values.items()})
        if method == "GET":
            url = f"{url}?{encoded}"
        else:
            data = encoded.encode()
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.load(exc)
        except Exception:
            detail = {"status": exc.code, "reason": exc.reason}
        raise MetaError(json.dumps(detail, ensure_ascii=False)) from exc
    if "error" in result:
        raise MetaError(json.dumps(result["error"], ensure_ascii=False))
    return result


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"posted_skus": [], "history": [], "pending": None}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def image_for(sku: str) -> Path | None:
    matches = sorted(path for path in IMAGE_DIR.glob(f"{sku}.*") if path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    return matches[0] if matches else None


def eligible_products() -> list[dict[str, str]]:
    with CATALOG.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    eligible = []
    for row in rows:
        try:
            in_stock = float(row["stock"] or 0) > 0
        except ValueError:
            in_stock = False
        image = image_for(row["sku"])
        if in_stock and image:
            eligible.append({**row, "image_path": image.relative_to(ROOT).as_posix()})
    return eligible


def natural_text(value: str) -> str:
    """Turn catalog all-caps text into readable Spanish without adding claims."""
    text = re.sub(r"\s+", " ", value.strip()).lower()
    replacements = {
        " generica ": " genérica ",
        " compas ": " compás ",
        " digitacion ": " digitación ",
        " estandard ": " estándar ",
        " lapiz ": " lápiz ",
        " liquido ": " líquido ",
        " pagina ": " página ",
        " boligrafo ": " bolígrafo ",
        " plastico ": " plástico ",
        " plastica ": " plástica ",
        " centimetros": " centímetros",
    }
    padded = f" {text} "
    for old, new in replacements.items():
        padded = padded.replace(old, new)
    return padded.strip()


def display_name(value: str) -> str:
    text = natural_text(value)
    text = re.sub(r"\s+(?:und|unid|unidad)$", "", text)
    text = text.replace("borrador pizarra blanca mag variedad", "borrador para pizarra blanca")
    text = text.replace("cartulina amarillo claro", "cartulina amarilla clara")
    text = text.replace("cartulina amarillo fuerte", "cartulina amarilla brillante")
    text = text.replace("cartulina verde claro", "cartulina verde clara")
    text = text.replace("cartulina naranja claro", "cartulina naranja clara")
    return text[:1].upper() + text[1:]


def caption_for(product: dict[str, str], variant: int) -> str:
    """Compose varied copy using only facts present in the catalog row."""
    name = display_name(product["name"])
    description = natural_text(product["description"]).rstrip(".")
    price = float(product["price_dop"])
    price_text = f"{price:,.2f}" if not price.is_integer() else f"{price:,.0f}"
    openings = [
        f"¿Te hace falta {name.lower()}? Lo tenemos disponible. 🙌",
        f"Para completar tu lista sin dar muchas vueltas: {name}. ✅",
        f"Un básico que siempre resuelve: {name}. ✨",
        f"Mira esta opción que tenemos en Papelería Sol Naciente: {name}. 👀",
        f"Si todavía te falta {name.lower()}, aquí lo encuentras. 📝",
        f"Para la escuela, la oficina o ese proyecto que tienes en mano: {name}. ✏️",
        f"Eso que te faltaba para seguir trabajando tranquilo: {name}. 🙌",
        f"Hoy te compartimos una opción práctica: {name}. 🌟",
    ]
    calls_to_action = [
        "Pasa por la papelería o escríbenos por DM para pedirlo. 💬",
        "¿Lo necesitas? Escríbenos y te ayudamos de una vez. 📩",
        "Agrégalo a tu lista y escríbenos para ordenar. 📝",
        "Date una vuelta por Papelería Sol Naciente o escríbenos por DM. 🛍️",
        "Estamos a la orden para ayudarte con tu pedido. 😊",
        "Escríbenos y con gusto te resolvemos. 💬",
    ]
    hashtags = {
        "MATERIAL ESCOLAR": "#MaterialEscolar #RegresoAClases #Papelería",
        "SERVICIOS": "#Servicios #Papelería #SantoDomingo",
    }.get(product["category"].strip().upper(), "#Papelería #Oficina #SantoDomingo")
    return (
        f"{openings[variant % len(openings)]}\n\n"
        f"{description[:1].upper() + description[1:]}.\n\n"
        f"💰 Precio: RD${price_text}\n"
        "📦 Disponible mientras haya existencias.\n\n"
        f"{calls_to_action[(variant * 5) % len(calls_to_action)]}\n\n"
        f"{hashtags} #PapeleriaSolNaciente"
    )


def campaign_slots() -> list[datetime]:
    slots = []
    day = CAMPAIGN_START
    while day <= CAMPAIGN_END:
        hours = (*POSTING_HOURS, *EXTRA_POSTING_HOURS_BY_DATE.get(day, ()))
        for hour in sorted(set(hours)):
            slots.append(datetime.combine(day, dt_time(hour), LOCAL_TZ))
        day += timedelta(days=1)
    return slots


def diversified(products: list[dict[str, str]]) -> list[dict[str, str]]:
    """Spread similar products across the week instead of grouping them together."""
    groups: dict[str, list[dict[str, str]]] = {}
    for product in products:
        key = natural_text(product["name"]).split()[0]
        groups.setdefault(key, []).append(product)
    ordered = []
    while groups:
        for key in list(groups):
            ordered.append(groups[key].pop(0))
            if not groups[key]:
                del groups[key]
    return ordered


def prepare_campaign(state: dict) -> None:
    products = eligible_products()
    already_posted = set(state.get("posted_skus", []))
    products = diversified([product for product in products if product["sku"] not in already_posted])
    slots = campaign_slots()
    if len(products) < len(slots):
        raise RuntimeError(f"Campaign needs {len(slots)} products, but only {len(products)} are eligible.")
    state["campaign"] = {
        "timezone": str(LOCAL_TZ),
        "starts": slots[0].isoformat(),
        "ends": slots[-1].isoformat(),
        "schedule": [
            {
                "scheduled_for": slot.isoformat(),
                "sku": product["sku"],
                "name": product["name"],
                "caption": caption_for(product, index + len(state.get("history", []))),
            }
            for index, (slot, product) in enumerate(zip(slots, products))
        ],
    }


def refresh_campaign_captions(state: dict) -> int:
    """Refresh copy for unposted campaign items without changing their schedule."""
    by_sku = {product["sku"]: product for product in eligible_products()}
    posted = set(state.get("posted_skus", []))
    schedule = state.get("campaign", {}).get("schedule", [])
    refreshed = 0
    for index, item in enumerate(schedule):
        product = by_sku.get(item["sku"])
        if product and item["sku"] not in posted:
            item["caption"] = caption_for(product, index + len(state.get("history", [])))
            refreshed += 1
    return refreshed


def fill_missing_campaign_slots(state: dict, today: date | None = None) -> int:
    """Add newly configured posting slots without changing existing assignments."""
    first_day = today or datetime.now(timezone.utc).astimezone(LOCAL_TZ).date()
    schedule = state.get("campaign", {}).get("schedule", [])
    existing_times = {item["scheduled_for"] for item in schedule}
    used_skus = {item["sku"] for item in schedule} | set(state.get("posted_skus", []))
    available = diversified([product for product in eligible_products() if product["sku"] not in used_skus])
    added = 0
    for slot in campaign_slots():
        if slot.date() < first_day:
            continue
        scheduled_for = slot.isoformat()
        if scheduled_for in existing_times:
            continue
        if not available:
            raise RuntimeError("Not enough eligible products to fill the missing campaign slots.")
        product = available.pop(0)
        schedule.append(
            {
                "scheduled_for": scheduled_for,
                "sku": product["sku"],
                "name": product["name"],
                "caption": caption_for(product, len(schedule) + len(state.get("history", []))),
            }
        )
        added += 1
    schedule.sort(key=lambda item: item["scheduled_for"])
    return added


def scheduled_time(item: dict) -> datetime:
    return datetime.fromisoformat(item["scheduled_for"]).astimezone(LOCAL_TZ)


def campaign_item(state: dict, now: datetime | None = None, due_only: bool = False) -> dict | None:
    """Return the next eligible unposted campaign item, optionally only if due."""
    local_now = (now or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
    eligible_skus = {product["sku"] for product in eligible_products()}
    posted = set(state.get("posted_skus", []))
    candidates = sorted(state.get("campaign", {}).get("schedule", []), key=lambda item: item["scheduled_for"])
    return next(
        (
            item
            for item in candidates
            if item["sku"] in eligible_skus
            and item["sku"] not in posted
            and (not due_only or scheduled_time(item) <= local_now)
        ),
        None,
    )


def campaign_post_due(state: dict, now: datetime | None = None) -> bool:
    pending = state.get("pending")
    if pending:
        scheduled_for = pending.get("scheduled_for")
        return not scheduled_for or datetime.fromisoformat(scheduled_for) <= (now or datetime.now(timezone.utc))
    return campaign_item(state, now=now, due_only=True) is not None


def new_pending(state: dict, now: datetime | None = None, due_only: bool = False) -> dict:
    products = eligible_products()
    if not products:
        raise RuntimeError("No in-stock products with matching images were found.")
    by_sku = {product["sku"]: product for product in products}
    posted = [sku for sku in state.get("posted_skus", []) if sku in by_sku]
    remaining = [product for product in products if product["sku"] not in posted]
    if not remaining:
        posted = []
        remaining = products
    queued = campaign_item(state, now=now, due_only=due_only)
    if due_only and queued is None:
        raise RuntimeError("No campaign post is due.")
    product = by_sku[queued["sku"]] if queued else remaining[0]
    image_url = f"{SITE_URL}/{urllib.parse.quote(product['image_path'], safe='/')}"
    return {
        "sku": product["sku"],
        "name": product["name"],
        "caption": queued["caption"] if queued else caption_for(product, len(state.get("history", []))),
        "scheduled_for": queued.get("scheduled_for") if queued else None,
        "image_url": image_url,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "facebook_post_id": None,
        "instagram_post_id": None,
    }


def publish_instagram(pending: dict, token: str, instagram_id: str) -> None:
    container = request_json(
        f"{instagram_id}/media",
        token,
        method="POST",
        values={"image_url": pending["image_url"], "caption": pending["caption"]},
    )["id"]
    for _ in range(20):
        status = request_json(container, token, values={"fields": "status_code"}).get("status_code")
        if status == "FINISHED":
            break
        if status in {"ERROR", "EXPIRED"}:
            raise MetaError(f"Instagram container {container} entered status {status}")
        time.sleep(3)
    else:
        raise MetaError(f"Instagram container {container} did not finish processing")
    pending["instagram_post_id"] = request_json(
        f"{instagram_id}/media_publish", token, method="POST", values={"creation_id": container}
    )["id"]


def publish_facebook(pending: dict, token: str, page_id: str) -> None:
    accounts = request_json(
        "me/accounts",
        token,
        values={"fields": "id,access_token", "limit": 100},
    ).get("data", [])
    page_token = next(
        (account.get("access_token") for account in accounts if account.get("id") == page_id),
        None,
    )
    if not page_token:
        raise MetaError(f"No Page access token was returned for Page {page_id}")
    result = request_json(
        f"{page_id}/photos",
        page_token,
        method="POST",
        values={"url": pending["image_url"], "caption": pending["caption"]},
    )
    pending["facebook_post_id"] = result.get("post_id") or result["id"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prepare-campaign", action="store_true")
    parser.add_argument("--refresh-captions", action="store_true")
    parser.add_argument("--fill-missing-slots", action="store_true")
    parser.add_argument("--enforce-window", action="store_true")
    args = parser.parse_args()
    state = load_state()
    if args.prepare_campaign:
        prepare_campaign(state)
        save_state(state)
        print(f"Prepared {len(state['campaign']['schedule'])} posts through {CAMPAIGN_END.isoformat()}.")
        return 0
    if args.refresh_captions:
        refreshed = refresh_campaign_captions(state)
        save_state(state)
        print(f"Refreshed {refreshed} unposted campaign captions.")
        return 0
    if args.fill_missing_slots:
        added = fill_missing_campaign_slots(state)
        save_state(state)
        print(f"Added {added} missing campaign slots.")
        return 0
    if args.enforce_window and not campaign_post_due(state):
        print("No campaign post is due; nothing to publish.")
        output("status", "skipped")
        return 0
    pending = state.get("pending") or new_pending(state, due_only=args.enforce_window)
    if args.dry_run:
        print(json.dumps(pending, ensure_ascii=False, indent=2))
        output("status", "dry-run")
        return 0

    token = os.environ["META_ACCESS_TOKEN"]
    page_id = os.environ["META_PAGE_ID"]
    instagram_id = os.environ["META_INSTAGRAM_ID"]
    state["pending"] = pending
    save_state(state)
    try:
        if not pending.get("instagram_post_id"):
            publish_instagram(pending, token, instagram_id)
            save_state(state)
        if not pending.get("facebook_post_id"):
            publish_facebook(pending, token, page_id)
            save_state(state)
    except Exception as exc:
        pending["last_error"] = str(exc)
        pending["last_error_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        print(f"Posting failed: {exc}", file=sys.stderr)
        output("status", "error")
        return 0

    pending["completed_at"] = datetime.now(timezone.utc).isoformat()
    pending.pop("last_error", None)
    pending.pop("last_error_at", None)
    state.setdefault("history", []).append(pending)
    state["history"] = state["history"][-250:]
    state.setdefault("posted_skus", []).append(pending["sku"])
    state["pending"] = None
    save_state(state)
    print(f"Published {pending['sku']} to Facebook and Instagram.")
    output("status", "success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
