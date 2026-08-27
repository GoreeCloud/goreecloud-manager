"""Core views for GoreeCloud Manager."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError, wait
from threading import BoundedSemaphore
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connections
from django.db.utils import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_safe

from core.request_context import get_request_id
from integrations.beszel import BeszelStatus, beszel_status
from integrations.everkeep import EverkeepSnapshot, everkeep_snapshot
from integrations.healthchecks import HealthchecksSnapshot, healthchecks_snapshot
from integrations.kopia import KopiaStatus, kopia_status
from integrations.netbird import NetBirdSnapshot, netbird_snapshot
from integrations.registry import integration_statuses
from integrations.tasks import TasksSnapshot, tasks_snapshot
from integrations.uptime_kuma import UptimeKumaSnapshot, uptime_kuma_snapshot

logger = logging.getLogger(__name__)
SnapshotFactory = Callable[[], Any]
FailureFactory = Callable[[str], Any]

MAX_OUTSTANDING_INTEGRATION_JOBS = 7
_INTEGRATION_EXECUTOR = ThreadPoolExecutor(
    max_workers=MAX_OUTSTANDING_INTEGRATION_JOBS,
    thread_name_prefix="manager-integration",
)
_INTEGRATION_SLOTS = BoundedSemaphore(MAX_OUTSTANDING_INTEGRATION_JOBS)


def _contained_detail(name: str) -> str:
    return (
        f"Unexpected {name} integration failure was contained by Manager. "
        "Inspect Manager logs before retrying or changing configuration."
    )


def _budget_detail(name: str) -> str:
    return (
        f"The {name} integration did not finish within Manager's request budget. "
        "Manager returned a safe fallback instead of waiting indefinitely."
    )


def _capacity_detail(name: str) -> str:
    return (
        f"The {name} integration could not start because Manager's bounded integration "
        "worker capacity is still occupied. Retry after current integration work finishes."
    )


def _netbird_failure(detail: str) -> NetBirdSnapshot:
    return NetBirdSnapshot(state="unavailable", detail=detail)


def _healthchecks_failure(detail: str) -> HealthchecksSnapshot:
    return HealthchecksSnapshot(state="unavailable", detail=detail)


def _uptime_kuma_failure(detail: str) -> UptimeKumaSnapshot:
    return UptimeKumaSnapshot(state="unavailable", detail=detail)


def _beszel_failure(detail: str) -> BeszelStatus:
    return BeszelStatus(state="unavailable", detail=detail)


def _kopia_failure(detail: str) -> KopiaStatus:
    return KopiaStatus(state="unavailable", detail=detail)


def _everkeep_failure(detail: str) -> EverkeepSnapshot:
    return EverkeepSnapshot(state="unavailable", detail=detail)


def _tasks_failure(detail: str) -> TasksSnapshot:
    return TasksSnapshot(
        state="unavailable",
        detail=detail,
        condition="internal-error",
    )


def _safe_snapshot(
    key: str,
    display_name: str,
    loader: SnapshotFactory,
    fallback_factory: FailureFactory,
    request_id: str,
) -> Any:
    """Contain one unexpected adapter failure without logging private exception text."""

    try:
        return loader()
    except Exception as exc:  # Adapter boundaries must fail soft for the Manager shell.
        logger.error(
            "integration_failure request_id=%s integration=%s exception_type=%s",
            request_id,
            key,
            type(exc).__name__,
        )
        return fallback_factory(_contained_detail(display_name))


def _submit_snapshot(
    key: str,
    display_name: str,
    loader: SnapshotFactory,
    fallback_factory: FailureFactory,
) -> Future[Any] | None:
    """Submit one integration job only when bounded worker capacity is available."""

    request_id = get_request_id()
    if not _INTEGRATION_SLOTS.acquire(blocking=False):
        logger.warning(
            "integration_capacity_exhausted request_id=%s integration=%s",
            request_id,
            key,
        )
        return None

    try:
        future = _INTEGRATION_EXECUTOR.submit(
            _safe_snapshot,
            key,
            display_name,
            loader,
            fallback_factory,
            request_id,
        )
    except Exception:
        _INTEGRATION_SLOTS.release()
        raise

    future.add_done_callback(lambda _future: _INTEGRATION_SLOTS.release())
    return future


def _overview_snapshots() -> dict[str, Any]:
    """Load read-only snapshots concurrently within a bounded Manager response budget."""

    integrations: dict[
        str,
        tuple[str, SnapshotFactory, FailureFactory],
    ] = {
        "everkeep": ("Everkeep", everkeep_snapshot, _everkeep_failure),
        "netbird": ("NetBird", netbird_snapshot, _netbird_failure),
        "healthchecks": ("Healthchecks", healthchecks_snapshot, _healthchecks_failure),
        "uptime_kuma": ("Uptime Kuma", uptime_kuma_snapshot, _uptime_kuma_failure),
        "beszel": ("Beszel", beszel_status, _beszel_failure),
        "kopia": ("Kopia", kopia_status, _kopia_failure),
        "tasks": ("GoreeCloud Tasks", tasks_snapshot, _tasks_failure),
    }

    snapshots: dict[str, Any] = {}
    futures: dict[str, tuple[Future[Any], str, FailureFactory]] = {}

    for key, (display_name, loader, fallback_factory) in integrations.items():
        future = _submit_snapshot(key, display_name, loader, fallback_factory)
        if future is None:
            snapshots[key] = fallback_factory(_capacity_detail(display_name))
            continue
        futures[key] = (future, display_name, fallback_factory)

    if futures:
        done, _not_done = wait(
            [item[0] for item in futures.values()],
            timeout=settings.MANAGER_INTEGRATION_BUDGET_SECONDS,
        )
        request_id = get_request_id()
        for key, (future, display_name, fallback_factory) in futures.items():
            if future in done:
                snapshots[key] = future.result()
                continue

            future.cancel()
            logger.warning(
                "integration_budget_exceeded request_id=%s integration=%s budget_seconds=%.3f",
                request_id,
                key,
                settings.MANAGER_INTEGRATION_BUDGET_SECONDS,
            )
            snapshots[key] = fallback_factory(_budget_detail(display_name))

    return snapshots


def _single_snapshot(
    key: str,
    display_name: str,
    loader: SnapshotFactory,
    fallback_factory: FailureFactory,
) -> Any:
    """Run one integration through the same bounded worker and response-budget contract."""

    future = _submit_snapshot(key, display_name, loader, fallback_factory)
    if future is None:
        return fallback_factory(_capacity_detail(display_name))

    try:
        return future.result(timeout=settings.MANAGER_INTEGRATION_BUDGET_SECONDS)
    except FutureTimeoutError:
        future.cancel()
        logger.warning(
            "integration_budget_exceeded request_id=%s integration=%s budget_seconds=%.3f",
            get_request_id(),
            key,
            settings.MANAGER_INTEGRATION_BUDGET_SECONDS,
        )
        return fallback_factory(_budget_detail(display_name))


@login_required
def overview(request):
    """Render the authenticated platform overview."""
    snapshots = _overview_snapshots()
    everkeep = snapshots["everkeep"]
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
                everkeep_status=everkeep.integration_status(),
                netbird_status=netbird.integration_status(),
                healthchecks_status=healthchecks.integration_status(),
                uptime_kuma_status=uptime_kuma.integration_status(),
                beszel_status=beszel.integration_status(),
                kopia_status=kopia.integration_status(),
                tasks_status=tasks.integration_status(),
            ),
            "everkeep": everkeep,
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
    tasks = _single_snapshot(
        "tasks",
        "GoreeCloud Tasks",
        tasks_snapshot,
        _tasks_failure,
    )
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

    snapshot = _single_snapshot(
        "tasks",
        "GoreeCloud Tasks",
        tasks_snapshot,
        _tasks_failure,
    )
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
