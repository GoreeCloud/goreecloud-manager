# GoreeCloud Infrastructure Status Integration

GoreeCloud Manager is a read-only observer of Gateway, DNS, and Network. It must not become the holder of Caddy administration credentials, DNS query/client data, NetBird/Network API credentials, peer inventory, route policy, or TLS private key material.

## Infrastructure Status v1

Manager consumes local, sanitized status documents for:

- `goreecloud-gateway` via `GOREECLOUD_GATEWAY_STATUS_FILE`;
- `goreecloud-dns` via `GOREECLOUD_DNS_STATUS_FILE`;
- `goreecloud-network` via `GOREECLOUD_NETWORK_STATUS_FILE`.

The parser is strict and fail-closed. It rejects unknown top-level or nested fields, unsupported schema/state values, mismatched producer identity, non-GoreeCloud runtime authority, malformed timestamps, undeclared sensitive-content exclusions, ambiguous acceptance metadata, duplicate capability IDs, and oversized documents.

## Approved content

Manager accepts only producer identity, UTC generation time, coarse service/capability state, explicit privacy guarantees, and explicit runtime/production acceptance booleans.

The contract explicitly excludes credentials, personal data, raw logs, network identifiers, DNS query data, and certificate material. Producers remain authoritative and must perform their own local normalization before Manager sees a document.

## Migration from direct NetBird access

`integrations/netbird.py` remains a transitional legacy adapter in this slice. The target product boundary is GoreeCloud Network's sanitized status document, after which direct NetBird API access and token handling can be removed from Manager.

## Runtime boundary

A valid status document is not proof that a service is production-ready. `runtime_acceptance_required` must remain true, and `production_approved` may become true only through the service's own accepted target-environment evidence. Manager never promotes a producer by inference.
