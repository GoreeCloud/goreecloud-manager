"""Core views for GoreeCloud Manager."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db import connections
from django.db.utils import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_safe

from integrations.beszel import BeszelStatus, beszel_status
from integrations.healthchecks import HealthchecksSnapshot, healthchecks_snapshot
from integrations.kopia import KopiaStatus, kopia_status
from integrations.netbird import NetBirdSnapshot, netbird_snapshot
from integrations.registry import integration_statuses
from integrations.tasks import TasksSnapshot, tasks_snapshot
from integrations.uptime_kuma import UptimeKumaSnapshot, uptime_kuma_snapshot

logger = logging.getLogger(__name__)
SnapshotFactory = Callable[[], Any]


def _contained_detail(name: str) -> str:
    return (
        f"Unexpected {name} integration failure was contained by Manager. "
        "Inspect Manager logs before retrying or changing configuration."
    )


def _netbird_failure() -> NetBirdSnapshot:
    return NetBirdSnapshot(state="unavailable", detail=_contained_detail("NetBird"))


def _healthchecks_failure() -> HealthchecksSnapshot:
    return HealthchecksSnapshot(
        state="unavailable", detail=_contained_detail("Healthchecks")
    )


def _uptime_kuma_failure() -> UptimeKumaSnapshot:
    return UptimeKumaSnapshot(
        state="unavailable", detail=_contained_detail("Uptime Kuma")
    )


def _beszel_failure() -> BeszelStatus:
    return BeszelStatus(state="unavailable", detail=_contained_detail("Beszel"))


def _kopia_failure() -> KopiaStatus:
    return KopiaStatus(state="unavailable", detail=_contained_detail("Kopia"))


def _tasks_failure() -> TasksSnapshot:
    return TasksSnapshot(
        state="unavailable",
        detail=_contained_detail("GoreeCloud Tasks"),
        condition="internal-error",
    )


def _safe_snapshot(
    name: str,
    loader: SnapshotFactory,
    fallback_factory: SnapshotFactory,
) -> Any:
    """Contain one unexpected adapter failure without logging private exception text."""

    try:
        return loader()
    except Exception as exc:  # Adapter boundaries must fail soft for the Manager shell.
        logger.error(
            "Contained unexpected %s integration failure (%s).",
            name,
            type(exc).__name__,
        )
        return fallback_factory()


def _overview_snapshots() -> dict[str, Any]:
    """Load independent read-only snapshots concurrently and contain adapter failures."""

    integrations: dict[str, tuple[SnapshotFactory, SnapshotFactory]] = {
        "netbird": (netbird_snapshot, _netbird_failure),
        "healthchecks": (healthchecks_snapshot, _healthchecks_failure),
        "uptime_kuma": (uptime_kuma_snapshot, _uptime_kuma_failure),
        "beszel": (beszel_status, _beszel_failure),
        "kopia": (kopia_status, _kopia_failure),
        "tasks": (tasks_snapshot, _tasks_failure),
    }

    with ThreadPoolExecutor(
        max_workers=len(integrations),
        thread_name_prefix="manager-integration",
    ) as executor:
        futures = {
            key: executor.submit(_safe_snapshot, key, loader, fallback)
            for key, (loader, fallback) in integrations.items()
        }
        return {key: future.result() for key, future in futures.items()}


@login_required
def overview(request):
    """Render the authenticated platform overview."""
    snapshots = _overview_snapshots()
    netbird = snapshots["netbird"]
    healthchecks = snapshots["healthchecks"]
    uptime_kuma = snapshots["uptime_kuma"]
    beszel = snapshots["beszel"]
    kopia = snapshots["kopia"]
    tasks = snapshots["tasks"]
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
    tasks = _safe_snapshot("tasks", tasks_snapshot, _tasks_failure)
    return render(
        request,
        "core/tasks.html",
        {
            "tasks": tasks,
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

    snapshot = _safe_snapshot("tasks", tasks_snapshot, _tasks_failure)
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
