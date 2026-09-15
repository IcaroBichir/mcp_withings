from __future__ import annotations

import json
import os
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

_ENV_FILE = Path.cwd() / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

CONFIG_DIR = Path.home() / ".config" / "withings-mcp"
TOKENS_FILE = CONFIG_DIR / "tokens.json"

_AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
_REDIRECT_PORT = 8766
_REDIRECT_URI = f"http://localhost:{_REDIRECT_PORT}"
_SCOPES = "user.info,user.metrics,user.activity"


class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code: str | None = None
    expected_state: str | None = None

    def do_GET(self) -> None:
        params = parse_qs(urlparse(self.path).query)
        state = params.get("state", [None])[0]
        if state != _CallbackHandler.expected_state:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization failed: invalid state parameter.</h1>")
            return
        _CallbackHandler.auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<h1>Authorization complete!</h1>"
            b"<p>You can close this tab and return to the terminal.</p>"
        )

    def log_message(self, *args) -> None:
        pass


def get_client_credentials() -> tuple[str, str]:
    """Return (client_id, client_secret) from env vars or raise."""
    client_id = os.environ.get("WITHINGS_CLIENT_ID")
    client_secret = os.environ.get("WITHINGS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "WITHINGS_CLIENT_ID and WITHINGS_CLIENT_SECRET must be set.\n"
            "Add them to a .env file in the working directory or export them as environment variables."
        )
    return client_id, client_secret


def run_oauth_flow(client_id: str, client_secret: str) -> dict:
    state = secrets.token_urlsafe(16)
    _CallbackHandler.expected_state = state

    query = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "state": state,
        "scope": _SCOPES,
        "redirect_uri": _REDIRECT_URI,
    })
    auth_url = f"{_AUTH_URL}?{query}"

    print("Opening browser for Withings authorization...")
    print(f"If the browser does not open, visit:\n  {auth_url}")
    webbrowser.open(auth_url)

    print(f"Waiting for callback on http://localhost:{_REDIRECT_PORT}... (times out in 2 minutes)")
    server = HTTPServer(("localhost", _REDIRECT_PORT), _CallbackHandler)
    server.timeout = 120
    server.handle_request()

    code = _CallbackHandler.auth_code
    if not code:
        raise RuntimeError(
            "No authorization code received — did the browser open? "
            "The flow times out after 2 minutes if no redirect is received."
        )

    print("Exchanging authorization code for tokens...")
    resp = httpx.post(_TOKEN_URL, data={
        "action": "requesttoken",
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": _REDIRECT_URI,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != 0:
        raise RuntimeError(f"Token exchange failed: status={data.get('status')} — {data.get('error', data)}")

    token_data = data["body"]
    _save(client_id, client_secret, token_data)
    return token_data


def _save(client_id: str, client_secret: str, token_data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    expires_in = token_data.get("expires_in", 10800)
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_at": time.time() + expires_in,
        "userid": token_data.get("userid"),
    }
    fd = os.open(TOKENS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(payload, indent=2))


def load_tokens() -> dict:
    if not TOKENS_FILE.exists():
        raise FileNotFoundError(
            "Not authenticated. Run `withings-mcp auth` to connect your Withings account."
        )
    return json.loads(TOKENS_FILE.read_text())


def refresh_if_needed() -> dict:
    tokens = load_tokens()
    if tokens["expires_at"] > time.time() + 60:
        return tokens

    resp = httpx.post(_TOKEN_URL, data={
        "action": "requesttoken",
        "grant_type": "refresh_token",
        "client_id": tokens["client_id"],
        "client_secret": tokens["client_secret"],
        "refresh_token": tokens["refresh_token"],
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != 0:
        raise RuntimeError(f"Token refresh failed: status={data.get('status')} — {data.get('error', data)}")

    new_data = data["body"]
    _save(tokens["client_id"], tokens["client_secret"], new_data)
    return {
        **tokens,
        "access_token": new_data["access_token"],
        "refresh_token": new_data["refresh_token"],
        "expires_at": time.time() + new_data.get("expires_in", 10800),
    }
