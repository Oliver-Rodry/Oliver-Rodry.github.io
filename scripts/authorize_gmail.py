#!/usr/bin/env python3
"""Authorize Gmail once and store OAuth values directly as GitHub secrets."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class OAuthHandler(BaseHTTPRequestHandler):
    result: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        OAuthHandler.result = {key: values[0] for key, values in query.items()}
        message = "Authorization received. You may close this tab and return to Terminal."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode())

    def log_message(self, *_args: object) -> None:
        return


def post_form(url: str, values: dict[str, str]) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(values).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def set_secret(gh: str, name: str, value: str, repo: str | None) -> None:
    command = [gh, "secret", "set", name]
    if repo:
        command.extend(["--repo", repo])
    subprocess.run(command, input=value, text=True, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", required=True, type=Path)
    parser.add_argument("--repo", help="Optional owner/repository target")
    args = parser.parse_args()

    document = json.loads(args.credentials.read_text(encoding="utf-8"))
    client = document.get("installed")
    if not client or not client.get("client_id") or not client.get("client_secret"):
        raise SystemExit("The JSON file is not a valid Desktop OAuth client credential.")

    server = HTTPServer(("127.0.0.1", 0), OAuthHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/"
    state = secrets.token_urlsafe(24)
    parameters = {
        "client_id": client["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = client.get("auth_uri", "https://accounts.google.com/o/oauth2/auth") + "?" + urllib.parse.urlencode(parameters)
    print("Opening Google authorization in your browser...")
    webbrowser.open(url)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout=300)
    server.server_close()
    result = OAuthHandler.result
    if result.get("state") != state or not result.get("code"):
        raise SystemExit(f"Authorization failed: {result.get('error', 'no authorization response')}")

    token = post_form(
        client.get("token_uri", "https://oauth2.googleapis.com/token"),
        {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "code": result["code"],
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    refresh_token = token.get("refresh_token")
    if not isinstance(refresh_token, str):
        raise SystemExit("Google did not return a refresh token. Revoke the app grant and try again with consent.")

    gh = shutil.which("gh") or "/opt/homebrew/bin/gh"
    set_secret(gh, "GMAIL_CLIENT_ID", client["client_id"], args.repo)
    set_secret(gh, "GMAIL_CLIENT_SECRET", client["client_secret"], args.repo)
    set_secret(gh, "GMAIL_REFRESH_TOKEN", refresh_token, args.repo)
    print("Success: Gmail OAuth credentials were stored as encrypted GitHub Actions secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
