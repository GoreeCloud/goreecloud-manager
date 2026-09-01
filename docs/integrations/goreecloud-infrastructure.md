# GoreeCloud Infrastructure Status Integration

GoreeCloud Manager is a read-only observer of Gateway, DNS, and Network. It must not become the holder of Caddy administration credentials, DNS query/client data, NetBird/Network API credentials, peer inventory, route policy, or TLS private key material.

## Infrastructure Status v1

Manager consumes local, sanitized status documents for:

- `goreecloud-gateway` via `GOREECLOUD_GATEWAY_STATUS_FILE`;
- `goreecloud-dns` via `GOREECLOUD_DNS_STATUS_FILE`;
- `goreecloud-network` via `GOREECLOUD_NETWORK_STATUS_FILE`.

The parser is strict and fail-closed. It rejects unknown top-level or nested fields, unsupported schema/state values, mismatched service identity, mismatched adapter identity, mismatched runtime authority, malformed timestamps, undeclared sensitive-content exclusions, ambiguous acceptance metadata, duplicate capability IDs, capability inventories that differ from the approved v1 producer contract, and oversized documents.

Infrastructure Status v1 binds each configured service to one exact producer tuple and one exact capability inventory:

- Gateway: `goreecloud-gateway/status-v1`, `GoreeCloud/CaddyDataPlane`, with `ingress`, `https`, `certificates`, and `publication`.
- DNS: `goreecloud-dns/status-v1`, `GoreeCloud/AdGuardHomeDataPlane`, with `resolver`, `filtering`, `encrypted-dns`, and `dns-policy`.
- Network: `goreecloud-network/status-v1`, `GoreeCloud/NetBirdDataPlane`, with `private-connectivity`, `peer-coordination`, `access-policy`, and `network-dns`.

Changing a v1 adapter identity, runtime authority, or capability inventory requires a coordinated producer/consumer contract change rather than silent acceptance by Manager. A future native data-plane authority transition must therefore be explicit and evidence-backed.

## Approved content

Manager accepts only producer identity, UTC generation time, coarse service/capability state, explicit privacy guarantees, and explicit runtime/production acceptance booleans.

The contract explicitly excludes credentials, personal data, raw logs, network identifiers, DNS query data, and certificate material. Producers remain authoritative and must perform their own local normalization before Manager sees a document.

## Migration from direct NetBird access

`integrations/netbird.py` remains a transitional legacy adapter in this slice. The target product boundary is GoreeCloud Network's sanitized status document, after which direct NetBird API access and token handling can be removed from Manager.

## Runtime boundary

A valid status document is not proof that a service is production-ready. `runtime_acceptance_required` must remain true, and `production_approved` may become true only through the service's own accepted target-environment evidence. Manager never promotes a producer by inference.
