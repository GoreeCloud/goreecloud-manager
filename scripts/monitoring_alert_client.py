#!/usr/bin/env python3
"""Disposable GoreeCloud Manager health and alert-transition assertions."""

from __future__ import annotations

import argparse
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MANAGER_URL = "https://manager.goreecloud.com/healthz/"
NTFY_BASE_URL = "http://ntfy"
TOPIC = "goreecloud-uptime"
CA_FILE = "/caddy-data/caddy/pki/authorities/local/root.crt"
PUBLISHER_TOKEN_FILE = "/run/secrets/ntfy_publisher_token"
SUBSCRIBER_TOKEN_FILE = "/run/secrets/ntfy_subscriber_token"

DOWN_TITLE = "GoreeCloud Manager DOWN"
DOWN_MESSAGE = "GoreeCloud Manager health endpoint is unavailable. Review Uptime Kuma and protected service logs."
UP_TITLE = "GoreeCloud Manager RECOVERED"
UP_MESSAGE = "GoreeCloud Manager health endpoint recovered."


def read_token(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def manager_status() -> tuple[int, dict | None]:
    context = ssl.create_default_context(cafile=CA_FILE)
    request = urllib.request.Request(MANAGER_URL, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except urllib.error.URLError:
        return 0, None


def require_up() -> None:
    status, payload = manager_status()
    expected = {"status": "ok", "service": "goreecloud-manager"}
    if status != 200 or payload != expected:
        raise SystemExit(f"expected healthy Manager endpoint, got status={status}, payload={payload!r}")
    print("Manager HTTPS health probe passed with verified disposable TLS and HTTP 200.")


def require_down() -> None:
    status, _ = manager_status()
    if status < 500:
        raise SystemExit(f"expected a server-side failure while Manager is stopped, got status={status}")
    print(f"Manager outage probe detected expected server-side failure status {status}.")


def ntfy_request(method: str, token: str | None, *, body: bytes | None = None, title: str | None = None):
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if title:
        headers["Title"] = title
    request = urllib.request.Request(
        f"{NTFY_BASE_URL}/{TOPIC}", data=body, headers=headers, method=method
    )
    return urllib.request.urlopen(request, timeout=10)


def publish(title: str, message: str) -> None:
    token = read_token(PUBLISHER_TOKEN_FILE)
    with ntfy_request("POST", token, body=message.encode("utf-8"), title=title) as response:
        if response.status not in (200, 201):
            raise SystemExit(f"unexpected ntfy publish status: {response.status}")
    print(f"Published sanitized transition: {title}")


def evaluate(expected: str) -> None:
    if expected == "down":
        require_down()
        publish(DOWN_TITLE, DOWN_MESSAGE)
    elif expected == "up":
        require_up()
        publish(UP_TITLE, UP_MESSAGE)
    else:
        raise SystemExit(f"unsupported transition: {expected}")


def read_messages() -> list[dict]:
    token = read_token(SUBSCRIBER_TOKEN_FILE)
    query = urllib.parse.urlencode({"poll": "1", "since": "all"})
    request = urllib.request.Request(
        f"{NTFY_BASE_URL}/{TOPIC}/json?{query}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read().decode("utf-8")
    return [
        event
        for line in data.splitlines()
        if line.strip()
        for event in [json.loads(line)]
        if event.get("event") == "message"
    ]


def assert_empty() -> None:
    messages = read_messages()
    if messages:
        raise SystemExit(f"expected no cached alert messages, found {len(messages)}")
    print("No alert was emitted while Manager was initially healthy.")


def assert_sequence(expected: list[str]) -> None:
    messages = read_messages()
    titles = [message.get("title") for message in messages]
    if titles != expected:
        raise SystemExit(f"unexpected alert title sequence: {titles!r}; expected {expected!r}")
    allowed_messages = {DOWN_MESSAGE, UP_MESSAGE}
    forbidden = (
        "Authorization",
        "Bearer ",
        "DJANGO_SECRET_KEY",
        "sessionid",
        "csrftoken",
        "admin_password",
        "TASKS_ACCESS_TOKEN",
    )
    for message in messages:
        if message.get("message", "") not in allowed_messages:
            raise SystemExit(f"unexpected alert body: {message.get('message')!r}")
        serialized = json.dumps(message, sort_keys=True)
        if any(marker in serialized for marker in forbidden):
            raise SystemExit("notification payload contains a forbidden sensitive marker")
    print(f"Validated alert transition sequence: {titles!r}")


def expect_http_denial(callable_, description: str) -> None:
    try:
        callable_()
    except urllib.error.HTTPError as exc:
        if exc.code not in (401, 403):
            raise SystemExit(f"{description} returned unexpected status {exc.code}") from exc
        print(f"{description} correctly denied with HTTP {exc.code}.")
        return
    raise SystemExit(f"{description} unexpectedly succeeded")


def publisher_cannot_read() -> None:
    token = read_token(PUBLISHER_TOKEN_FILE)
    query = urllib.parse.urlencode({"poll": "1", "since": "all"})
    def call():
        request = urllib.request.Request(
            f"{NTFY_BASE_URL}/{TOPIC}/json?{query}",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        urllib.request.urlopen(request, timeout=10)
    expect_http_denial(call, "write-only monitor subscriber attempt")


def subscriber_cannot_publish() -> None:
    token = read_token(SUBSCRIBER_TOKEN_FILE)
    def call():
        with ntfy_request("POST", token, body=b"should-not-publish", title="denied"):
            pass
    expect_http_denial(call, "read-only subscriber publish attempt")


def anonymous_cannot_read() -> None:
    query = urllib.parse.urlencode({"poll": "1", "since": "all"})
    def call():
        urllib.request.urlopen(f"{NTFY_BASE_URL}/{TOPIC}/json?{query}", timeout=10)
    expect_http_denial(call, "anonymous alert subscription")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe-up")
    sub.add_parser("assert-empty")
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("state", choices=("down", "up"))
    sequence_parser = sub.add_parser("assert-sequence")
    sequence_parser.add_argument("states", nargs="+", choices=("down", "up"))
    sub.add_parser("publisher-cannot-read")
    sub.add_parser("subscriber-cannot-publish")
    sub.add_parser("anonymous-cannot-read")
    args = parser.parse_args()

    if args.command == "probe-up":
        require_up()
    elif args.command == "assert-empty":
        assert_empty()
    elif args.command == "evaluate":
        evaluate(args.state)
    elif args.command == "assert-sequence":
        mapping = {"down": DOWN_TITLE, "up": UP_TITLE}
        assert_sequence([mapping[state] for state in args.states])
    elif args.command == "publisher-cannot-read":
        publisher_cannot_read()
    elif args.command == "subscriber-cannot-publish":
        subscriber_cannot_publish()
    else:
        anonymous_cannot_read()


if __name__ == "__main__":
    main()
