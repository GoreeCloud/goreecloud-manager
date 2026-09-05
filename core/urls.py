"""Core application routes."""

from django.urls import path

from . import everkeep_views, platform_events, privacy_views, views

urlpatterns = [
    path("", views.overview, name="overview"),
    path("platform/", views.platform_view, name="platform"),
    path("platform/events/", platform_events.platform_events, name="platform-events"),
    path("everkeep/", everkeep_views.everkeep_view, name="everkeep"),
    path("privacy-shield/", privacy_views.privacy_shield, name="privacy-shield"),
    path("tasks/", views.tasks_view, name="tasks"),
    path("healthz/", views.healthz, name="healthz"),
    path("readyz/", views.readyz, name="readyz"),
    path(
        "healthz/integrations/tasks/",
        views.tasks_integration_healthz,
        name="tasks-integration-healthz",
    ),
]
