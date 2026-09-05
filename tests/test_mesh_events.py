"""Tests for Manager's bounded authenticated GoreeCloud Mesh event consumer."""

import json
import os
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from integrations.mesh_events import (
    RELATIONSHIP_UPSERTED,
    SERVICE_UPSERTED,
    iter_mesh_event_refresh_signals,
    mesh_event_stream_status,
)


class _StreamResponse:
    def __init__(self, lines, *, status_code=200, content_type="text/event-stream; charset=utf-8"):
        self._lines = list(lines)
        self.status_code = status_code
        self.headers = {"content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_lines(self):
        yield from self._lines


class MeshEventAdapterTests(SimpleTestCase):
    EVENT_TOKEN = "mesh-events-test-token-0123456789abcdef0123456789abcdef"
    PLATFORM_TOKEN = "mesh-platform-test-token-abcdef0123456789abcdef0123456789"

    def _environment(self, **overrides):
        values = {
            "MESH_API_URL": "https://mesh.internal.example.test",
            "MESH_ACCESS_TOKEN": self.PLATFORM_TOKEN,
            "MESH_EVENTS_ENABLED": "true",
            "MESH_EVENTS_ACCESS_TOKEN": self.EVENT_TOKEN,
            "MESH_EVENTS_ACCESS_TOKEN_FILE": "",
            "MESH_EVENTS_BUFFER_SIZE": "8",
            "MESH_EVENTS_WINDOW_SECONDS": "5",
        }
        values.update(overrides)
        return patch.dict(os.environ, values, clear=False)

    def _event(self, event_type=SERVICE_UPSERTED):
        if event_type == SERVICE_UPSERTED:
            source = "goreecloud-manager"
            subject = source
            data = {"health": "healthy"}
        else:
            source = "goreecloud-manager"
            subject = "manager-to-mesh"
            data = {"target": "goreecloud-mesh", "type": "platform-coordination"}
        return {
            "schema": "goreecloud.mesh.event.v1",
            "id": "evt-7",
            "type": event_type,
            "source": source,
            "subject": subject,
            "data": data,
            "created_at": "2026-09-05T00:00:00Z",
            "authority_transfer": False,
        }

    def _frame(self, payload, *, event_type=None):
        name = event_type or payload["type"]
        return [
            ": goreecloud-mesh live-only best-effort event stream",
            "",
            f"event: {name}",
            f"data: {json.dumps(payload, separators=(',', ':'))}",
            "",
            ": stream-window-complete; reconnect without replay guarantees",
            "",
        ]

    @patch("integrations.mesh_events.httpx.stream")
    def test_registered_event_becomes_minimal_platform_refresh_signal(self, mocked_stream):
        mocked_stream.return_value = _StreamResponse(self._frame(self._event()))

        with self._environment():
            signals = list(iter_mesh_event_refresh_signals())

        self.assertEqual(
            signals,
            ['event: platform-update\ndata: {"type":"mesh.service.upserted.v1"}\n\n'],
        )
        call = mocked_stream.call_args
        self.assertEqual(call.args[:2], ("GET", "https://mesh.internal.example.test/v1/events/stream"))
        self.assertEqual(call.kwargs["headers"]["Authorization"], f"Bearer {self.EVENT_TOKEN}")
        self.assertNotEqual(call.kwargs["headers"]["Authorization"], f"Bearer {self.PLATFORM_TOKEN}")
        self.assertEqual(
            call.kwargs["params"],
            [
                ("type", SERVICE_UPSERTED),
                ("type", RELATIONSHIP_UPSERTED),
                ("buffer", "8"),
                ("window_seconds", "5"),
            ],
        )
        self.assertNotIn(self.EVENT_TOKEN, signals[0])
        self.assertNotIn("goreecloud-manager", signals[0])
        self.assertNotIn("healthy", signals[0])
        self.assertNotIn("evt-7", signals[0])

    @patch("integrations.mesh_events.httpx.stream")
    def test_relationship_event_is_accepted_without_copying_relationship_data(self, mocked_stream):
        payload = self._event(RELATIONSHIP_UPSERTED)
        mocked_stream.return_value = _StreamResponse(self._frame(payload))

        with self._environment():
            signals = list(iter_mesh_event_refresh_signals())

        self.assertEqual(len(signals), 1)
        self.assertIn(RELATIONSHIP_UPSERTED, signals[0])
        self.assertNotIn("goreecloud-mesh", signals[0])
        self.assertNotIn("platform-coordination", signals[0])

    @patch("integrations.mesh_events.httpx.stream")
    def test_disabled_event_consumer_makes_no_network_request(self, mocked_stream):
        with self._environment(MESH_EVENTS_ENABLED="false"):
            status = mesh_event_stream_status()
            signals = list(iter_mesh_event_refresh_signals())

        self.assertEqual(status.state, "disabled")
        self.assertEqual(signals, [])
        mocked_stream.assert_not_called()

    @patch("integrations.mesh_events.httpx.stream")
    def test_event_and_platform_registry_credentials_remain_separate(self, mocked_stream):
        mocked_stream.return_value = _StreamResponse(self._frame(self._event()))
        with self._environment():
            list(iter_mesh_event_refresh_signals())
        authorization = mocked_stream.call_args.kwargs["headers"]["Authorization"]
        self.assertEqual(authorization, f"Bearer {self.EVENT_TOKEN}")
        self.assertNotIn(self.PLATFORM_TOKEN, authorization)

    @patch("integrations.mesh_events.httpx.stream")
    def test_invalid_event_token_fails_closed_before_network(self, mocked_stream):
        with self._environment(MESH_EVENTS_ACCESS_TOKEN="secret\r\nInjected: value"):
            status = mesh_event_stream_status()
            signals = list(iter_mesh_event_refresh_signals())

        self.assertEqual(status.state, "misconfigured")
        self.assertNotIn("secret", status.detail)
        self.assertEqual(signals, [])
        mocked_stream.assert_not_called()

    @patch("integrations.mesh_events.httpx.stream")
    def test_non_loopback_plain_http_fails_closed_before_network(self, mocked_stream):
        with self._environment(MESH_API_URL="http://mesh.internal.example.test"):
            status = mesh_event_stream_status()
            signals = list(iter_mesh_event_refresh_signals())

        self.assertEqual(status.state, "misconfigured")
        self.assertIn("HTTPS", status.detail)
        self.assertEqual(signals, [])
        mocked_stream.assert_not_called()

    @patch("integrations.mesh_events.httpx.stream")
    def test_upstream_non_success_and_wrong_content_type_are_fail_soft(self, mocked_stream):
        mocked_stream.return_value = _StreamResponse([], status_code=403)
        with self._environment():
            self.assertEqual(list(iter_mesh_event_refresh_signals()), [])

        mocked_stream.return_value = _StreamResponse([], content_type="application/json")
        with self._environment():
            self.assertEqual(list(iter_mesh_event_refresh_signals()), [])

    @patch("integrations.mesh_events.httpx.stream")
    def test_replay_id_field_is_rejected(self, mocked_stream):
        payload = self._event()
        lines = [
            f"event: {SERVICE_UPSERTED}",
            "id: evt-7",
            f"data: {json.dumps(payload)}",
            "",
        ]
        mocked_stream.return_value = _StreamResponse(lines)
        with self._environment():
            self.assertEqual(list(iter_mesh_event_refresh_signals()), [])

    @patch("integrations.mesh_events.httpx.stream")
    def test_unknown_event_type_and_authority_transfer_fail_closed(self, mocked_stream):
        payload = self._event()
        payload["type"] = "mesh.service.deleted.v1"
        mocked_stream.return_value = _StreamResponse(
            self._frame(payload, event_type="mesh.service.deleted.v1")
        )
        with self._environment():
            self.assertEqual(list(iter_mesh_event_refresh_signals()), [])

        payload = self._event()
        payload["authority_transfer"] = True
        mocked_stream.return_value = _StreamResponse(self._frame(payload))
        with self._environment():
            self.assertEqual(list(iter_mesh_event_refresh_signals()), [])

    @patch("integrations.mesh_events.httpx.stream")
    def test_unexpected_payload_fields_fail_closed(self, mocked_stream):
        payload = self._event()
        payload["data"]["private_detail"] = "must-not-cross-boundary"
        mocked_stream.return_value = _StreamResponse(self._frame(payload))
        with self._environment():
            signals = list(iter_mesh_event_refresh_signals())
        self.assertEqual(signals, [])

    @patch("integrations.mesh_events.httpx.stream")
    def test_invalid_bounds_fail_closed_before_network(self, mocked_stream):
        with self._environment(MESH_EVENTS_BUFFER_SIZE="65"):
            status = mesh_event_stream_status()
            signals = list(iter_mesh_event_refresh_signals())
        self.assertEqual(status.state, "misconfigured")
        self.assertEqual(signals, [])
        mocked_stream.assert_not_called()

        with self._environment(MESH_EVENTS_WINDOW_SECONDS="11"):
            status = mesh_event_stream_status()
            signals = list(iter_mesh_event_refresh_signals())
        self.assertEqual(status.state, "misconfigured")
        self.assertEqual(signals, [])
        mocked_stream.assert_not_called()
