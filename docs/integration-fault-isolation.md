# Integration Fault Isolation

GoreeCloud Manager treats read-only integrations as independent visibility sources. An unexpected software defect, malformed edge case, or uncaught adapter exception in one integration must not make the entire administrative shell unavailable.

## Overview loading model

The authenticated overview loads these six independent read-only snapshots concurrently:

- NetBird
- Healthchecks
- Uptime Kuma
- Beszel
- Kopia
- GoreeCloud Tasks

Concurrent loading prevents normal upstream timeout budgets from accumulating serially across the dashboard. The page remains bounded primarily by the slowest individual integration instead of the sum of all integration waits.

Each existing adapter remains responsible for its normal expected failure modes, including disabled configuration, invalid configuration, authentication rejection, protocol errors, unavailable endpoints, malformed responses, and stale delegated artifacts.

## Unexpected exception boundary

Manager adds one final fault-containment boundary around each adapter call. If an exception escapes an adapter unexpectedly:

1. Manager records only the integration key and exception class in its application log.
2. The raw exception message is not logged by this boundary because it may contain an upstream URL, credential fragment, path, response detail, or other private information.
3. Manager replaces the failed call with the integration's normal typed snapshot object in an `unavailable` state.
4. The overview continues rendering the other integrations.
5. The displayed detail tells the administrator that an unexpected integration failure was contained and that Manager logs should be inspected before configuration is changed.

This broad exception boundary is intentionally limited to the top-level integration orchestration layer. It is not a replacement for precise exception handling inside the individual adapters.

## GoreeCloud Tasks surfaces

The same containment boundary applies to the standalone GoreeCloud Tasks page and its sanitized monitoring endpoint.

If an unexpected Tasks adapter failure occurs:

- the Tasks page continues to render and reports that live task data is unavailable;
- the monitoring endpoint returns HTTP `503`;
- the monitoring payload reports `state: unavailable` and `condition: internal-error`;
- raw exception text is not included in the response.

## Authority and security boundaries

This change does not increase Manager authority. Integrations remain read-only, existing credentials and network boundaries remain unchanged, Manager receives no Docker socket or arbitrary shell capability, and authoritative state remains in the source systems.

Fault isolation is a presentation and operational-resilience control. It does not convert a failed integration into a healthy state and does not make external integration health part of Manager's generic `/readyz/` container readiness signal.
