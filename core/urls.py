"""Core application routes."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.overview, name="overview"),
    path("tasks/", views.tasks_view, name="tasks"),
    path("healthz/", views.healthz, name="healthz"),
    path("readyz/", views.readyz, name="readyz"),
    path(
        "healthz/integrations/tasks/",
        views.tasks_integration_healthz,
        name="tasks-integration-healthz",
    ),
]
