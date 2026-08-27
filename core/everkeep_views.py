"""Authenticated read-only Everkeep resilience visibility."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.everkeep_presenter import present_everkeep
from core.views import _everkeep_failure, _single_snapshot
from integrations.everkeep import everkeep_snapshot


@login_required
def everkeep_view(request):
    """Render only the sanitized Everkeep resilience contract."""
    snapshot = _single_snapshot(
        "everkeep",
        "Everkeep",
        everkeep_snapshot,
        _everkeep_failure,
    )
    return render(
        request,
        "core/everkeep.html",
        {
            "everkeep": present_everkeep(snapshot),
            "release": "0.1.0-dev",
        },
    )
