"""Core views for GoreeCloud Manager."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from integrations.beszel import beszel_status
from integrations.healthchecks import healthchecks_snapshot
from integrations.kopia import kopia_status
from integrations.netbird import netbird_snapshot
from integrations.registry import integration_statuses
from integrations.tasks import tasks_snapshot
from integrations.uptime_kuma import uptime_kuma_snapshot


@login_required
def overview(request):
    """Render the authenticated platform overview."""
    netbird = netbird_snapshot()
    healthchecks = healthchecks_snapshot()
    uptime_kuma = uptime_kuma_snapshot()
    beszel = beszel_status()
    kopia = kopia_status()
    tasks = tasks_snapshot()
    return render(
        request,
        "core/overview.html",
        {
            "integrations": integration_statuses(
                netbird_status=netbird.integration_status(),
                healthchecks_status=healthchecks.integration_status(),
                uptime_kuma_status=uptime_kuma.integration_status(),
                beszel_status=beszel.integration_status(),
                kopia_status=kopia.integration_status(),
                tasks_status=tasks.integration_status(),
            ),
            "netbird": netbird,
            "healthchecks": healthchecks,
            "uptime_kuma": uptime_kuma,
            "beszel": beszel,
            "kopia": kopia,
            "tasks": tasks,
            "release": "0.1.0-dev",
        },
    )


@login_required
def tasks_view(request):
    """Render authorization-scoped GoreeCloud operational work from Tasks."""
    return render(
        request,
        "core/tasks.html",
        {
            "tasks": tasks_snapshot(),
            "release": "0.1.0-dev",
        },
    )


def healthz(request):
    """Return a minimal liveness response without exposing private state."""
    return JsonResponse({"status": "ok", "service": "goreecloud-manager"})
