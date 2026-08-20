"""Privacy Shield status views for GoreeCloud Manager."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from integrations.privacy_shield import privacy_shield_snapshot


@login_required
def privacy_shield(request):
    """Render sanitized, read-only Privacy Shield capability status."""
    snapshot = privacy_shield_snapshot()
    return render(
        request,
        "core/privacy_shield.html",
        {
            "privacy_shield": snapshot,
            "release": "0.1.0-dev",
        },
    )
