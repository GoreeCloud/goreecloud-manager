"""Core views for GoreeCloud Manager."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from integrations.registry import integration_statuses


@login_required
def overview(request):
    """Render the authenticated platform overview."""
    return render(
        request,
        "core/overview.html",
        {
            "integrations": integration_statuses(),
            "release": "0.1.0-dev",
        },
    )


def healthz(request):
    """Return a minimal liveness response without exposing private state."""
    return JsonResponse({"status": "ok", "service": "goreecloud-manager"})
