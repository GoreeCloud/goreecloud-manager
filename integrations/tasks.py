"""Read-only GoreeCloud Tasks integration for GoreeCloud Manager.

Manager consumes only the dedicated Tasks Manager API. It never connects directly to the
Tasks database and never receives a user password or a write-capable Tasks credential.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0
MANAGER_API_PATH = "/api/v1/manager/operational-tasks/"
EXPECTED_SCHEMA = "goreecloud.tasks.manager.v1"
EXPECTED_VERSION = 1


@dataclass(frozen=True)
class ManagerTask:
    """Data-minimized operational task fields approved for Manager display."""

    task_id: int
    title: str
    project_id: int
    project_name: str
    priority: int
    priority_label: str
    status: str
    status_label: str
    due_at: datetime | None
    assigned_system: str
    assigned_service: str
    environment: str
    workload_category: str
    blocker: str
    resume_condition: str
    backup_required: bool
    recovery_required: bool
    validation_required: bool
    documentation_required: bool
    related_change_record: str
    related_documentation: str
    updated_at: datetime


@dataclass(frozen=True)
class TasksSnapshot:
    """Fail-soft normalized GoreeCloud Tasks integration state."""

    state: str
    detail: str
    condition: str = "unknown"
    tasks: tuple[ManagerTask, ...] = ()
    total_open: int = 0
    blocked: int = 0
    p0: int = 0
    p1: int = 0
    identity: str = ""
    observed_at: datetime | None = None

    @property
    def returned(self) -> int:
        return len(self.tasks)

    def integration_status(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}

    def monitoring_status(self) -> dict[str, str]:
        """Return the data-minimized state approved for integration monitoring."""

        return {"state": self.state, "condition": self.condition}


class TasksProtocolError(ValueError):
    """Raised when Tasks returns data that Manager cannot safely normalize."""


def _enabled() -> bool:
    return os.getenv("TASKS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _timeout_seconds() -> float:
    raw = os.getenv("TASKS_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return min(value, MAX_TIMEOUT_SECONDS)


def _configured_token() -> tuple[str | None, str | None]:
    direct = os.getenv("TASKS_ACCESS_TOKEN", "").strip()
    file_path = os.getenv("TASKS_ACCESS_TOKEN_FILE", "").strip()

    if direct and file_path:
        return None, "Set only one Tasks access-token source."
    if file_path:
        try:
            token = Path(file_path).read_text(encoding="utf-8").strip()
        except OSError:
            return None, "The configured Tasks access-token file could not be read."
        if not token:
            return None, "The configured Tasks access-token file is empty."
        return token, None
    if direct:
        return direct, None
    return None, "Missing TASKS_ACCESS_TOKEN or TASKS_ACCESS_TOKEN_FILE."


def _api_url() -> tuple[str | None, str | None]:
    base_url = os.getenv("TASKS_API_URL", "").strip().rstrip("/")
    if not base_url:
        return None, "Missing TASKS_API_URL."

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, "TASKS_API_URL must be an absolute HTTP(S) URL."
    if parsed.username or parsed.password:
        return None, "TASKS_API_URL must not embed credentials."
    return f"{base_url}{MANAGER_API_PATH}", None


def _parse_timestamp(value: Any, *, required: bool = False) -> datetime | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TasksProtocolError("Tasks returned an invalid timestamp.")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise TasksProtocolError("Tasks returned an invalid timestamp.") from exc
    if parsed.tzinfo is None:
        raise TasksProtocolError("Tasks returned a timestamp without a timezone.")
    return parsed


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise TasksProtocolError(f"Tasks returned an invalid {field} value.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise TasksProtocolError(f"Tasks returned an invalid {field} value.") from exc
    if parsed < 0:
        raise TasksProtocolError(f"Tasks returned an invalid {field} value.")
    return parsed


def _text(value: Any, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise TasksProtocolError("Tasks returned a non-text field where text was expected.")
    value = value.strip()
    if required and not value:
        raise TasksProtocolError("Tasks returned a required blank text field.")
    return value


def _normalize_task(raw: Any) -> ManagerTask:
    if not isinstance(raw, dict):
        raise TasksProtocolError("Tasks returned a task entry that was not an object.")

    project = raw.get("project")
    priority = raw.get("priority")
    status = raw.get("status")
    requirements = raw.get("requirements")
    if not all(isinstance(value, dict) for value in (project, priority, status, requirements)):
        raise TasksProtocolError("Tasks returned an incomplete operational task object.")

    requirement_fields = ("backup", "recovery", "validation", "documentation")
    if any(not isinstance(requirements.get(field), bool) for field in requirement_fields):
        raise TasksProtocolError("Tasks returned invalid operational requirement flags.")

    return ManagerTask(
        task_id=_nonnegative_int(raw.get("id"), "task id"),
        title=_text(raw.get("title"), required=True),
        project_id=_nonnegative_int(project.get("id"), "project id"),
        project_name=_text(project.get("name"), required=True),
        priority=_nonnegative_int(priority.get("value"), "priority"),
        priority_label=_text(priority.get("label"), required=True),
        status=_text(status.get("value"), required=True),
        status_label=_text(status.get("label"), required=True),
        due_at=_parse_timestamp(raw.get("due_at")),
        assigned_system=_text(raw.get("assigned_system")),
        assigned_service=_text(raw.get("assigned_service")),
        environment=_text(raw.get("environment")),
        workload_category=_text(raw.get("workload_category")),
        blocker=_text(raw.get("blocker")),
        resume_condition=_text(raw.get("resume_condition")),
        backup_required=requirements["backup"],
        recovery_required=requirements["recovery"],
        validation_required=requirements["validation"],
        documentation_required=requirements["documentation"],
        related_change_record=_text(raw.get("related_change_record")),
        related_documentation=_text(raw.get("related_documentation")),
        updated_at=_parse_timestamp(raw.get("updated_at"), required=True),
    )


def _healthy_snapshot(payload: Any) -> TasksSnapshot:
    if not isinstance(payload, dict):
        raise TasksProtocolError("Tasks returned an unexpected response.")
    if payload.get("schema") != EXPECTED_SCHEMA or payload.get("version") != EXPECTED_VERSION:
        raise TasksProtocolError("Tasks returned an unsupported Manager API schema.")

    authorization = payload.get("authorization")
    summary = payload.get("summary")
    tasks_raw = payload.get("tasks")
    if not isinstance(authorization, dict) or not isinstance(summary, dict) or not isinstance(tasks_raw, list):
        raise TasksProtocolError("Tasks returned an incomplete Manager API response.")

    identity = _text(authorization.get("identity"), required=True)
    observed_at = _parse_timestamp(payload.get("generated_at"), required=True)
    total_open = _nonnegative_int(summary.get("total_open"), "total_open")
    blocked = _nonnegative_int(summary.get("blocked"), "blocked")
    p0 = _nonnegative_int(summary.get("p0"), "p0")
    p1 = _nonnegative_int(summary.get("p1"), "p1")
    returned = _nonnegative_int(summary.get("returned"), "returned")
    tasks = tuple(_normalize_task(item) for item in tasks_raw)

    if returned != len(tasks) or total_open < returned:
        raise TasksProtocolError("Tasks returned inconsistent Manager API counts.")
    if any(count > total_open for count in (blocked, p0, p1)):
        raise TasksProtocolError("Tasks returned impossible Manager API summary counts.")

    detail = f"Live authorization-scoped Tasks API data verified for {total_open} open operational task(s)."
    return TasksSnapshot(
        state="healthy",
        detail=detail,
        condition="healthy",
        tasks=tasks,
        total_open=total_open,
        blocked=blocked,
        p0=p0,
        p1=p1,
        identity=identity,
        observed_at=observed_at,
    )


def tasks_snapshot() -> TasksSnapshot:
    """Query GoreeCloud Tasks and return a normalized operational-work snapshot."""

    if not _enabled():
        return TasksSnapshot(
            state="disabled",
            detail="Disabled until the scoped GoreeCloud Tasks integration is explicitly enabled.",
            condition="disabled",
        )

    api_url, url_error = _api_url()
    token, token_error = _configured_token()
    configuration_errors = [error for error in (url_error, token_error) if error]
    if configuration_errors:
        return TasksSnapshot(
            state="misconfigured",
            detail=" ".join(configuration_errors),
            condition="misconfigured",
        )

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "goreecloud-manager/0.1",
    }

    try:
        response = httpx.get(api_url, headers=headers, timeout=_timeout_seconds())
    except httpx.TimeoutException:
        return TasksSnapshot(
            state="unavailable",
            detail="GoreeCloud Tasks did not respond before the configured timeout.",
            condition="unreachable",
        )
    except httpx.RequestError:
        return TasksSnapshot(
            state="unavailable",
            detail="Manager could not reach the configured GoreeCloud Tasks API endpoint.",
            condition="unreachable",
        )

    if response.status_code == 401:
        return TasksSnapshot(
            state="unavailable",
            detail="GoreeCloud Tasks rejected the configured integration credential.",
            condition="authentication-rejected",
        )
    if response.status_code == 403:
        return TasksSnapshot(
            state="unavailable",
            detail="GoreeCloud Tasks denied the configured integration request.",
            condition="authorization-denied",
        )
    if response.status_code == 404:
        return TasksSnapshot(
            state="unavailable",
            detail="The configured GoreeCloud Tasks Manager API endpoint is not available.",
            condition="endpoint-unavailable",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        return TasksSnapshot(
            state="unavailable",
            detail=f"GoreeCloud Tasks API returned HTTP {response.status_code}.",
            condition="upstream-error",
        )

    try:
        return _healthy_snapshot(response.json())
    except (ValueError, TasksProtocolError):
        return TasksSnapshot(
            state="unavailable",
            detail="GoreeCloud Tasks returned a response Manager could not safely interpret.",
            condition="schema-invalid",
        )
