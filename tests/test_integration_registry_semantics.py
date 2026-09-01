from integrations.registry import integration_statuses


def _by_key(statuses: list[dict[str, str]], key: str) -> dict[str, str]:
    return next(status for status in statuses if status["key"] == key)


def test_unrecognized_live_adapter_state_fails_neutral() -> None:
    statuses = integration_statuses(
        netbird_status={"state": "connected", "detail": "Transport is reachable."}
    )

    netbird = _by_key(statuses, "netbird")
    assert netbird["state"] == "unknown"
    assert "unrecognized semantic state" in netbird["detail"]
    assert "connected" not in netbird["detail"]


def test_recognized_live_adapter_state_is_preserved() -> None:
    statuses = integration_statuses(
        healthchecks_status={"state": "healthy", "detail": "Read-only source verified."}
    )

    healthchecks = _by_key(statuses, "healthchecks")
    assert healthchecks["state"] == "healthy"
    assert healthchecks["detail"] == "Read-only source verified."


def test_candidate_producer_consumes_only_service_availability() -> None:
    statuses = integration_statuses(
        gateway_status={
            "availability": "degraded",
            "availability_reason": "partial_backend_health",
            "configuration_state": "valid",
            "connectivity": "connected",
            "security": "secure",
        }
    )

    gateway = _by_key(statuses, "gateway")
    assert gateway["state"] == "degraded"
    assert "partial_backend_health" in gateway["detail"]
    assert "connected" not in gateway["detail"]
    assert "secure" not in gateway["detail"]
    assert "valid" not in gateway["detail"]


def test_candidate_producer_does_not_infer_availability_from_readiness() -> None:
    statuses = integration_statuses(
        beacon_status={
            "configuration_state": "valid",
            "pipeline_state": "complete",
            "production_authority": "inherited",
        }
    )

    beacon = _by_key(statuses, "beacon")
    assert beacon["state"] == "unknown"
    assert "service-availability" in beacon["detail"]


def test_connectivity_like_candidate_availability_is_rejected() -> None:
    statuses = integration_statuses(
        conduit_status={
            "availability": "connected",
            "availability_reason": "transport_reachable",
        }
    )

    conduit = _by_key(statuses, "conduit")
    assert conduit["state"] == "unknown"
    assert "connected" not in conduit["detail"]
    assert "transport_reachable" not in conduit["detail"]


def test_candidate_producers_are_not_shown_without_observed_payloads() -> None:
    keys = {status["key"] for status in integration_statuses()}

    assert "gateway" not in keys
    assert "beacon" not in keys
    assert "conduit" not in keys
