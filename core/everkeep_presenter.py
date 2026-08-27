"""Privacy-minimized presentation model for Everkeep resilience status."""

from __future__ import annotations

from dataclasses import dataclass

from integrations.everkeep import EverkeepSnapshot

_CAPABILITY_LABELS = {
    "backup-integrity": "Backup integrity",
    "restore-readiness": "Restore readiness",
    "recovery-readiness": "Recovery readiness",
    "portability": "Portability",
    "portability-continuity": "Portability continuity",
    "preservation": "Preservation",
    "succession": "Succession and digital legacy",
}


@dataclass(frozen=True)
class EverkeepCapabilityView:
    label: str
    state: str


@dataclass(frozen=True)
class EverkeepViewModel:
    state: str
    message: str
    generated_at: str
    recovery_readiness: str
    backup_verification: str
    backup_verification_age: str
    portability_continuity: str
    preservation: str
    capabilities: tuple[EverkeepCapabilityView, ...]
    production_approved: bool


def _age_label(seconds: int | None) -> str:
    if seconds is None:
        return "Not reported"
    if seconds < 60:
        return f"{seconds} seconds ago"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = seconds // 86400
    return f"{days} day{'s' if days != 1 else ''} ago"


def _capability_label(capability_id: str) -> str:
    """Return a bounded display label without reflecting arbitrary producer text."""
    return _CAPABILITY_LABELS.get(capability_id, "Additional resilience capability")


def present_everkeep(snapshot: EverkeepSnapshot) -> EverkeepViewModel:
    """Convert the strict status contract into a display-only, privacy-minimized model."""
    if snapshot.state == "unavailable":
        message = snapshot.detail
    else:
        message = (
            "Read-only resilience status from the approved Everkeep adapter. "
            "Backup contents, file inventories, private paths, credentials, recovery secrets, "
            "personal records, and raw legacy records are excluded by contract."
        )

    return EverkeepViewModel(
        state=snapshot.state,
        message=message,
        generated_at=snapshot.generated_at or "Not reported",
        recovery_readiness=snapshot.recovery_readiness,
        backup_verification=snapshot.backup_verification,
        backup_verification_age=_age_label(snapshot.backup_verification_age_seconds),
        portability_continuity=snapshot.portability_continuity,
        preservation=snapshot.preservation,
        capabilities=tuple(
            EverkeepCapabilityView(
                label=_capability_label(capability.id),
                state=capability.state,
            )
            for capability in snapshot.capabilities
        ),
        production_approved=snapshot.production_approved,
    )
