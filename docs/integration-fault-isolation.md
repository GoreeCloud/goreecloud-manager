# Integration Fault Isolation

GoreeCloud Manager treats read-only integrations as independent visibility sources. An unexpected software defect, malformed edge case, uncaught adapter exception, or excessively slow adapter must not make the entire administrative shell unavailable.

## Overview loading model

The authenticated overview loads these six independent read-only snapshots concurrently:

- NetBird
- Healthchecks
- Uptime Kuma
- Beszel
- Kopia
- GoreeCloud Tasks

Concurrent loading prevents normal upstream timeout budgets from accumulating serially across the dashboard. Manager also applies its own response budget, so the page is no longer required to wait for the slowest adapter indefinitely.

Each existing adapter remains responsible for its normal expected failure modes, including disabled configuration, invalid configuration, authentication rejection, protocol errors, unavailable endpoints, malformed responses, adapter-specific timeouts, and stale delegated artifacts.

## Bounded integration executor

Each Gunicorn worker owns a six-slot integration executor. Manager acquires a slot before submitting work and releases it only when that future completes or is cancelled before it begins. If every slot is already occupied, Manager does not enqueue additional work into ThreadPoolExecutor's otherwise unbounded queue. The requesting surface receives a typed `unavailable` fallback immediately.

`MANAGER_INTEGRATION_BUDGET_SECONDS` bounds how long the Overview, standalone Tasks page, and Tasks monitoring endpoint wait for integration work. The default is seven seconds and deployment input greater than twenty seconds is rejected. When the budget expires, Manager stops waiting, attempts to cancel work that has not started, and returns a sanitized fallback. Work that is already running may finish under the adapter's own timeout rules, but it continues to occupy one of the six bounded slots until completion.

This design deliberately bounds both request waiting and outstanding integration concurrency. It does not pretend that Python can safely terminate an arbitrary running integration thread.

## Unexpected exception boundary

Manager adds one final fault-containment boundary around each adapter call. If an exception escapes an adapter unexpectedly:

1. Manager records only the server-generated request ID, integration key, and exception class in its application log.
2. The raw exception message is not logged by this boundary because it may contain an upstream URL, credential fragment, path, response detail, or other private information.
3. Manager replaces the failed call with the integration's normal typed snapshot object in an `unavailable` state.
4. The overview continues rendering the other integrations.
5. The displayed detail tells the administrator that an unexpected integration failure was contained and that Manager logs should be inspected before configuration is changed.

This broad exception boundary is intentionally limited to the top-level integration orchestration layer. It is not a replacement for precise exception handling inside the individual adapters.

## Request correlation

Every Django response receives a new server-generated `X-Request-ID`. Manager ignores caller-supplied request IDs and passes only its own correlation value into integration failure, budget, and capacity log events. The production Gunicorn access-log format records the same response header while omitting query strings and other unnecessary request metadata.

## GoreeCloud Tasks surfaces

The same containment and request-budget boundaries apply to the standalone GoreeCloud Tasks page and its sanitized monitoring endpoint.

If an unexpected Tasks adapter failure, Manager-level budget expiry, or bounded-capacity condition occurs:

- the Tasks page continues to render and reports that live task data is unavailable;
- the monitoring endpoint returns HTTP `503`;
- the monitoring payload reports `state: unavailable` and `condition: internal-error`;
- raw exception text, token values, request query strings, and upstream response bodies are not included in the response.

## Authority and security boundaries

This change does not increase Manager authority. Integrations remain read-only, existing credentials and network boundaries remain unchanged, Manager receives no Docker socket or arbitrary shell capability, and authoritative state remains in the source systems.

Fault isolation is a presentation and operational-resilience control. It does not convert a failed integration into a healthy state and does not make external integration health part of Manager's generic `/readyz/` container readiness signal.
