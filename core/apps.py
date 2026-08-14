from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self) -> None:
        """Register GoreeCloud Manager signal handlers once the app registry is ready."""

        from core import auth_events  # noqa: F401
