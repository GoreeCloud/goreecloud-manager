"""Authenticated same-origin refresh stream for the Manager Platform Overview."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET

from integrations.mesh_events import iter_mesh_event_refresh_signals, mesh_event_stream_status


@login_required
@require_GET
def platform_events(request):
    """Proxy only sanitized Mesh lifecycle refresh signals to an authenticated browser.

    The browser never receives the GoreeCloud Identity service credential or the raw
    Mesh lifecycle envelope. A 204 response is used for disabled or invalid local
    configuration so EventSource does not retry a configuration error indefinitely.
    Runtime/upstream failures end an already-open best-effort stream and may reconnect
    without replay guarantees, matching the Mesh event transport contract.
    """

    status = mesh_event_stream_status()
    if status.state != "configured":
        response = HttpResponse(status=204)
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    response = StreamingHttpResponse(
        iter_mesh_event_refresh_signals(),
        content_type="text/event-stream; charset=utf-8",
    )
    response["Cache-Control"] = "no-store"
    response["X-Accel-Buffering"] = "no"
    response["X-Content-Type-Options"] = "nosniff"
    return response
