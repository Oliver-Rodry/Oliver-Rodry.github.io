#!/usr/bin/env python3
"""Publish an in-stock catalog product to Facebook and Instagram."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "products.csv"
IMAGE_DIR = ROOT / "img" / "products"
STATE = ROOT / ".github" / "social-posting-state.json"
SITE_URL = "https://papeleriasolnaciente.com"
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"


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
            eligible.append({**row, "image_path": str(image.relative_to(ROOT))})
    return eligible


def caption_for(product: dict[str, str], variant: int) -> str:
    name = product["name"].strip().title()
    description = product["description"].strip().capitalize()
    price = float(product["price_dop"])
    price_text = f"{price:,.2f}" if not price.is_integer() else f"{price:,.0f}"
    openings = [
        f"✨ ¡Tenemos {name} disponible!",
        f"📚 Lo que necesitas para estudiar y trabajar: {name}.",
        f"🛍️ Conoce nuestro producto destacado: {name}.",
        f"✅ Ya puedes conseguir {name} en Papelería Sol Naciente.",
    ]
    hashtags = {
        "MATERIAL ESCOLAR": "#MaterialEscolar #RegresoAClases #Papelería",
        "SERVICIOS": "#Servicios #Papelería #SantoDomingo",
    }.get(product["category"].strip().upper(), "#Papelería #Oficina #SantoDomingo")
    return (
        f"{openings[variant % len(openings)]}\n\n"
        f"{description}\n\n"
        f"💰 Precio: RD${price_text}\n"
        "📦 Disponible mientras haya existencias.\n\n"
        "Escríbenos para ordenar o visítanos. 💬\n\n"
        f"{hashtags} #PapeleriaSolNaciente"
    )


def new_pending(state: dict) -> dict:
    products = eligible_products()
    if not products:
        raise RuntimeError("No in-stock products with matching images were found.")
    by_sku = {product["sku"]: product for product in products}
    posted = [sku for sku in state.get("posted_skus", []) if sku in by_sku]
    remaining = [product for product in products if product["sku"] not in posted]
    if not remaining:
        posted = []
        remaining = products
    product = remaining[0]
    image_url = f"{SITE_URL}/{urllib.parse.quote(product['image_path'], safe='/')}"
    return {
        "sku": product["sku"],
        "name": product["name"],
        "caption": caption_for(product, len(state.get("history", []))),
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
    args = parser.parse_args()
    state = load_state()
    pending = state.get("pending") or new_pending(state)
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
