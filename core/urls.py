"""Core application routes."""

from django.urls import path

from . import everkeep_views, privacy_views, views

urlpatterns = [
    path("", views.overview, name="overview"),
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
