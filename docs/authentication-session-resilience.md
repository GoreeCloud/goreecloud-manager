# Authentication and Session Resilience

## Purpose

GoreeCloud Manager is a private administrative application. Authentication remains required even when the application is reached through GoreeCloud private networking. This document defines the source-level session and authentication stability contract without claiming that target-environment access controls or production evidence are complete.

## Session Storage

Manager explicitly uses Django's database-backed session engine.

This keeps the authoritative session record on the server and preserves normal Django logout invalidation. Manager intentionally does not switch to Django's local-memory cache for session storage because that cache is not multi-process safe and is not appropriate for the current multi-worker Gunicorn runtime.

The current session settings are:

- `SESSION_ENGINE=django.contrib.sessions.backends.db`.
- `SESSION_COOKIE_NAME=goreecloud_manager_sessionid`.
- `SESSION_COOKIE_HTTPONLY=True`.
- `SESSION_COOKIE_SAMESITE=Lax`.
- `SESSION_COOKIE_SECURE=True` whenever `DJANGO_DEBUG=false`.
- `SESSION_SAVE_EVERY_REQUEST=False` so ordinary read-only Manager navigation does not create an SQLite session write on every request.

## Session Expiration Window

Manager defaults to an eight-hour server-side session expiration window.

`DJANGO_SESSION_COOKIE_AGE_SECONDS` may configure the window, but startup fails closed when the value is below 900 seconds or above 86400 seconds. The allowed range is therefore 15 minutes through 24 hours.

Django calculates session expiration from the session's last modification. A legitimate operation that modifies session data can therefore establish a new expiration point. Manager deliberately keeps `SESSION_SAVE_EVERY_REQUEST=False`, so ordinary read-only navigation does not modify the session merely to extend its expiry and does not add an SQLite session write on every request.

`DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE` defaults to `true` and is parsed strictly: recognized true/false forms are accepted and unrecognized text fails closed during settings initialization. Browser-close expiration is an additional boundary rather than the sole lifetime control because some browsers may restore browser sessions. The server-side expiration window remains bounded even when the browser preserves its cookie.

## Session Fixation and Logout

Manager relies on Django's authentication session behavior and keeps regression coverage around it:

- Successful login rotates the pre-authentication session key while retaining permitted anonymous session data.
- Logout is POST-only.
- Logout flushes the server-side session record and removes authenticated access.
- A password change invalidates an already authenticated session when its stored authentication hash no longer matches the user record.

These behaviors are tested as stability and security invariants rather than assumed from framework defaults.

## Login Redirect Safety

The login form now preserves Django's `next` destination so an administrator who is redirected to sign in can return to the originally requested internal Manager page.

Django's LoginView safe-redirect validation remains authoritative. Regression coverage verifies that an external `next` URL is rejected and falls back to the configured Manager overview rather than becoming an open redirect.

## Cache and CSRF Boundary

The login response remains non-cacheable through Django's authentication view behavior, and regression coverage verifies `no-store` and `no-cache` response directives.

Manager also uses a distinct `goreecloud_manager_csrftoken` cookie and sets `CSRF_COOKIE_HTTPONLY=True`. Current Manager forms render CSRF tokens server-side and do not require browser JavaScript to read the CSRF cookie.

## Authentication Event Logging

Manager records three sanitized authentication events through Django authentication signals:

- `auth_login_succeeded`
- `auth_login_failed`
- `auth_logout`

Events include the server-generated Manager request correlation ID. Successful login and logout events may include the internal database user ID needed for operator correlation.

Authentication logs deliberately exclude:

- submitted usernames on failed login;
- passwords;
- raw credential dictionaries;
- IP addresses;
- forwarded-for values;
- user-agent strings;
- query strings;
- caller-supplied request identifiers.

Regression coverage submits synthetic secret-like values and verifies that they do not appear in captured authentication logs.

## Login-Abuse Control Boundary

This pass does not claim complete brute-force or credential-stuffing protection.

A process-local Django cache limiter was deliberately not added because the current Gunicorn runtime uses multiple workers and Django documents the local-memory cache as not multi-process safe. Adding a fake per-process lockout would create misleading security evidence. A shared rate-limit control must be selected and validated as an explicit target-environment control, or implemented with a deliberately shared authoritative store, before Manager claims login-abuse protection.

The private NetBird/Caddy publication boundary remains a separate required defense and also remains subject to target-environment validation.

## Validation Contract

Source validation for this increment must demonstrate:

1. bounded session settings load with the documented defaults;
2. unsafe session-age values fail closed;
3. unrecognized browser-close boolean input fails closed;
4. pre-authentication session keys rotate on successful login;
5. logout requires POST and removes the active server-side session;
6. changing a user's password invalidates an existing session;
7. internal `next` destinations are preserved;
8. external `next` destinations are rejected;
9. the login response is not cacheable;
10. failed-login logs exclude submitted credentials;
11. successful login and logout logs expose no username or password.

The permanent CI, runtime publication, backup/restore, upgrade/rollback, monitoring/alert, and production-readiness-evidence workflows remain the acceptance gates for the exact pull-request head.

## Production Boundary

Passing these source and disposable-environment checks does not approve production deployment. It does not satisfy target-environment DNS, HTTPS, NetBird policy, credentials, backup repository, monitoring registration, or operator acceptance evidence.
