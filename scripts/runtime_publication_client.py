#!/usr/bin/env python3
"""Client-side assertions for disposable GoreeCloud Manager private publication."""

from __future__ import annotations

import http.cookiejar
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "manager.goreecloud.com"
BASE_URL = f"https://{HOST}"
CA_PATH = Path("/caddy-data/caddy/pki/authorities/local/root.crt")
ADMIN_PASSWORD_PATH = Path("/run/secrets/admin_password")
CSRF_RE = re.compile(rb'name="csrfmiddlewaretoken" value="([^"]+)"')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def tls_context() -> ssl.SSLContext:
    if not CA_PATH.is_file():
        raise AssertionError(f"disposable Caddy CA is unavailable at {CA_PATH}")
    return ssl.create_default_context(cafile=str(CA_PATH))


def opener(*, cookie_jar: http.cookiejar.CookieJar | None = None, redirects: bool = True):
    handlers: list[urllib.request.BaseHandler] = [
        urllib.request.HTTPSHandler(context=tls_context())
    ]
    if cookie_jar is not None:
        handlers.append(urllib.request.HTTPCookieProcessor(cookie_jar))
    if not redirects:
        handlers.append(NoRedirect())
    return urllib.request.build_opener(*handlers)


def request(
    http_opener,
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
):
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers=headers or {},
        method=method,
    )
    try:
        with http_opener.open(req, timeout=8) as response:
            return response.status, response.headers, response.read(), response.geturl()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read(), exc.geturl()


def assert_tls() -> None:
    context = tls_context()
    with socket.create_connection((HOST, 443), timeout=8) as raw:
        with context.wrap_socket(raw, server_hostname=HOST) as tls_socket:
            negotiated = tls_socket.version()
            peer = tls_socket.getpeercert()

    if not negotiated or not negotiated.startswith("TLS"):
        raise AssertionError(f"unexpected TLS negotiation result: {negotiated!r}")
    sans = set(peer.get("subjectAltName", ()))
    if ("DNS", HOST) not in sans:
        raise AssertionError(f"verified TLS certificate does not contain {HOST!r}: {sorted(sans)!r}")
    print(f"Verified private TLS and hostname using {negotiated}.")


def assert_approved() -> None:
    address = socket.gethostbyname(HOST)
    if not address.startswith("100."):
        raise AssertionError(f"private hostname resolved outside synthetic NetBird range: {address}")

    jar = http.cookiejar.CookieJar()
    follow = opener(cookie_jar=jar, redirects=True)
    no_redirect = opener(cookie_jar=jar, redirects=False)

    status, headers, body, _ = request(no_redirect, "/healthz/")
    if status != 200:
        raise AssertionError(f"approved client health request returned {status}, expected 200")
    payload = json.loads(body.decode("utf-8"))
    if payload != {"status": "ok", "service": "goreecloud-manager"}:
        raise AssertionError(f"unexpected health response: {payload!r}")
    if headers.get("X-Content-Type-Options") != "nosniff":
        raise AssertionError("security middleware did not set X-Content-Type-Options: nosniff")

    status, headers, _, _ = request(no_redirect, "/")
    if status != 302:
        raise AssertionError(f"unauthenticated root request returned {status}, expected 302")
    if not headers.get("Location", "").startswith("/login/"):
        raise AssertionError(f"unexpected login redirect: {headers.get('Location')!r}")

    status, headers, body, _ = request(follow, "/login/")
    if status != 200:
        raise AssertionError(f"login page returned {status}, expected 200")
    match = CSRF_RE.search(body)
    if match is None:
        raise AssertionError("login page did not contain a CSRF token")
    csrf_token = match.group(1).decode("utf-8")

    set_cookies = headers.get_all("Set-Cookie", [])
    csrf_headers = [value for value in set_cookies if "csrftoken=" in value]
    if not csrf_headers:
        raise AssertionError("login response did not issue a CSRF cookie")
    if not all("Secure" in value and "SameSite=Lax" in value for value in csrf_headers):
        raise AssertionError(f"CSRF cookie missing Secure/SameSite=Lax: {csrf_headers!r}")

    password = ADMIN_PASSWORD_PATH.read_text(encoding="utf-8").strip()
    if not password:
        raise AssertionError("synthetic admin password secret is empty")
    form = urllib.parse.urlencode(
        {
            "username": "synthetic-admin",
            "password": password,
            "csrfmiddlewaretoken": csrf_token,
            "next": "/",
        }
    ).encode("utf-8")
    status, headers, _, _ = request(
        no_redirect,
        "/login/",
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/login/",
        },
        data=form,
    )
    if status != 302 or headers.get("Location") != "/":
        raise AssertionError(
            f"synthetic login returned status={status} location={headers.get('Location')!r}"
        )

    session_headers = [
        value for value in headers.get_all("Set-Cookie", []) if "sessionid=" in value
    ]
    if not session_headers:
        raise AssertionError("successful login did not issue a session cookie")
    if not all(
        "Secure" in value and "HttpOnly" in value and "SameSite=Lax" in value
        for value in session_headers
    ):
        raise AssertionError(
            f"session cookie missing Secure/HttpOnly/SameSite=Lax: {session_headers!r}"
        )

    status, _, body, _ = request(follow, "/")
    if status != 200:
        raise AssertionError(f"authenticated Overview returned {status}, expected 200")
    if b"GoreeCloud Manager" not in body:
        raise AssertionError("authenticated Overview did not render the Manager identity")

    print("Approved private client, authentication, and secure-cookie assertions passed.")


def assert_denied() -> None:
    denied = opener(redirects=False)
    for path in ("/healthz/", "/login/"):
        status, _, body, _ = request(
            denied,
            path,
            headers={"X-Forwarded-For": "100.100.0.10"},
        )
        if status != 403:
            raise AssertionError(
                f"unapproved client with spoofed X-Forwarded-For reached {path!r}: {status}"
            )
        if body.strip() != b"Forbidden":
            raise AssertionError(f"unexpected denial body for {path!r}: {body!r}")
    print("Unapproved-source denial and spoof-resistance assertions passed.")


def assert_isolation() -> None:
    for hostname in ("manager", "goreecloud-manager"):
        try:
            addresses = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            continue
        raise AssertionError(
            f"private client unexpectedly resolved internal backend {hostname!r}: {addresses!r}"
        )
    print("Direct Manager backend isolation assertions passed.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: runtime_publication_client.py approved|denied|tls|isolation")
    actions = {
        "approved": assert_approved,
        "denied": assert_denied,
        "tls": assert_tls,
        "isolation": assert_isolation,
    }
    try:
        assertion = actions[sys.argv[1]]
    except KeyError as exc:
        raise SystemExit(f"unsupported action: {sys.argv[1]}") from exc
    assertion()


if __name__ == "__main__":
    main()
