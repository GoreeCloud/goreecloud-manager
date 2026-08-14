"""Core views for GoreeCloud Manager."""

from django.contrib.auth.decorators import login_required
from django.db import connections
from django.db.utils import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_safe

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


def _no_store_json(payload: dict[str, str], *, status: int = 200) -> JsonResponse:
    """Return a minimal operational JSON response that intermediaries must not cache."""
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    return response


@require_safe
def healthz(request):
    """Return process liveness without coupling it to databases or integrations."""
    return _no_store_json({"status": "ok", "service": "goreecloud-manager"})


@require_safe
def readyz(request):
    """Return readiness based only on Manager-owned state required to serve requests."""
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
    except DatabaseError:
        return _no_store_json(
            {"status": "unavailable", "service": "goreecloud-manager"},
            status=503,
        )

    if not row or row[0] != 1:
        return _no_store_json(
            {"status": "unavailable", "service": "goreecloud-manager"},
            status=503,
        )

    return _no_store_json({"status": "ready", "service": "goreecloud-manager"})


@require_GET
def tasks_integration_healthz(request):
    """Return a sanitized health signal for the read-only GoreeCloud Tasks integration."""

    snapshot = tasks_snapshot()
    monitoring = snapshot.monitoring_status()
    is_healthy = monitoring["condition"] == "healthy"
    return _no_store_json(
        {
            "status": "ok" if is_healthy else "unhealthy",
            "service": "goreecloud-manager",
            "integration": "goreecloud-tasks",
            "state": monitoring["state"],
            "condition": monitoring["condition"],
        },
        status=200 if is_healthy else 503,
    )
