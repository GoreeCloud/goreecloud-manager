"""Gunicorn runtime contract for GoreeCloud Manager."""

bind = "0.0.0.0:8000"
workers = 2
worker_class = "sync"

# Final process-level guard. Normal integration responses are bounded more tightly by
# Manager's own integration request budget, but a wedged request must still be killed.
timeout = 30
graceful_timeout = 30
keepalive = 2

# Periodic worker recycling limits the lifetime of accidental process-local leaks while
# jitter avoids recycling both workers on the same request count.
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
capture_output = True

# Do not log query strings, request headers, cookies, client addresses, or user identity.
# The response correlation ID lets application containment logs be matched to access logs.
access_log_format = (
    'time="%(t)s" level=INFO logger=gunicorn.access '
    'request_id=%({x-request-id}o)s method=%(m)s path=%(U)s '
    'status=%(s)s duration_us=%(D)s pid=%(p)s'
)
