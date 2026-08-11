"""WSGI entry point for GoreeCloud Manager."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "goreecloud_manager.settings")
application = get_wsgi_application()
