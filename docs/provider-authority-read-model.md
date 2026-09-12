# GoreeCloud Manager — Privacy Shield and Everkeep Read Model

**Lifecycle:** Development source candidate  
**Roadmap:** FR-005

Manager may present bounded producer-authoritative privacy and recovery evidence, but it must never become Privacy Shield or Everkeep authority.

The source adapter validates the exact producer system, canonical repository, exact producer revision, authority domain, assertion family, evidence reference, payload SHA-256, observation/validity window, minimized-data flags, and `authority_transfer: false` before Manager can present a record.

The provider-owned outcome remains opaque to Manager. Manager derives only whether the producer record is current or stale for display. It does not convert a Privacy Shield outcome into privacy authorization, does not convert an Everkeep outcome into recoverability, and does not combine provider outcomes into a stronger platform state.

Every normalized view is bound to one explicit evaluation instant. Direct view construction cannot label expired evidence as current, and future-dated evidence fails closed.

## Latest-record selection

`select_latest_provider_evidence` may select one latest record from a bounded local collection of at most 128 producer records. Every candidate is independently normalized against the same evaluation instant before selection; an invalid older record is not silently ignored.

Selection is by exact observation time only. When multiple records share the latest observation time, their revision, provider-owned outcome, validity boundary, evidence reference, and payload digest must describe the same exact evidence. Conflicting same-time records are ambiguous and fail closed rather than being arbitrarily ordered, merged, voted on, or converted into a stronger Manager-owned state.

This is selection, not authority aggregation. Duplicate evidence cannot create additional confidence or authorization.

Stale evidence is shown as attention and cannot be treated as current truth. Future-dated evidence, invalid validity windows, wrong repositories, wrong authority domains, extended record shapes, sensitive-content flags, malformed digests, ambiguous latest evidence, and authority-transfer attempts fail closed.

This source slice performs no network request and creates no production integration claim. Live provider transport, authenticated Mesh delivery, deployed provider acceptance, exact runtime evidence, Manager UI adoption, production acceptance, and Stable qualification remain separate gates.
