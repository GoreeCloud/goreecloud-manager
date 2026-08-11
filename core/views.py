"""Core views for GoreeCloud Manager."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from integrations.healthchecks import healthchecks_snapshot
from integrations.kopia import kopia_status
from integrations.netbird import netbird_snapshot
from integrations.registry import integration_statuses
from integrations.uptime_kuma import uptime_kuma_snapshot


@login_required
def overview(request):
    """Render the authenticated platform overview."""
    netbird = netbird_snapshot()
    healthchecks = healthchecks_snapshot()
    uptime_kuma = uptime_kuma_snapshot()
    kopia = kopia_status()
    return render(
        request,
        "core/overview.html",
        {
            "integrations": integration_statuses(
                netbird_status=netbird.integration_status(),
                healthchecks_status=healthchecks.integration_status(),
                uptime_kuma_status=uptime_kuma.integration_status(),
                kopia_status=kopia.integration_status(),
            ),
            "netbird": netbird,
            "healthchecks": healthchecks,
            "uptime_kuma": uptime_kuma,
            "kopia": kopia,
            "release": "0.1.0-dev",
        },
    )


def healthz(request):
    """Return a minimal liveness response without exposing private state."""
    return JsonResponse({"status": "ok", "service": "goreecloud-manager"})
