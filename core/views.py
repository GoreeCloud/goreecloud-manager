"""Core views for GoreeCloud Manager."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from integrations.netbird import netbird_snapshot
from integrations.registry import integration_statuses


@login_required
def overview(request):
    """Render the authenticated platform overview."""
    netbird = netbird_snapshot()
    return render(
        request,
        "core/overview.html",
        {
            "integrations": integration_statuses(
                netbird_status=netbird.integration_status()
            ),
            "netbird": netbird,
            "release": "0.1.0-dev",
        },
    )


def healthz(request):
    """Return a minimal liveness response without exposing private state."""
    return JsonResponse({"status": "ok", "service": "goreecloud-manager"})
