"""Small request-boundary middleware for GoreeCloud Manager."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from django.http import HttpRequest, HttpResponse

from core.request_context import reset_request_id, set_request_id


class RequestContextMiddleware:
    """Assign a server-generated correlation ID without trusting caller-supplied IDs."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = uuid4().hex
        token = set_request_id(request_id)
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)
