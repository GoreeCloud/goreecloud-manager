# GoreeCloud Manager — Privacy Shield and Everkeep Read Model

**Lifecycle:** Development source candidate  
**Roadmap:** FR-005

Manager may present bounded producer-authoritative privacy and recovery evidence, but it must never become Privacy Shield or Everkeep authority.

The source adapter validates the exact producer system, canonical repository, exact producer revision, authority domain, assertion family, evidence reference, payload SHA-256, observation/validity window, minimized-data flags, and `authority_transfer: false` before Manager can present a record.

The provider-owned outcome remains opaque to Manager. Manager derives only whether the producer record is current or stale for display. It does not convert a Privacy Shield outcome into privacy authorization, does not convert an Everkeep outcome into recoverability, and does not combine provider outcomes into a stronger platform state.

Stale evidence is shown as attention and cannot be treated as current truth. Future-dated evidence, invalid validity windows, wrong repositories, wrong authority domains, extended record shapes, sensitive-content flags, malformed digests, and authority-transfer attempts fail closed.

This source slice performs no network request and creates no production integration claim. Live provider transport, authenticated Mesh delivery, deployed provider acceptance, exact runtime evidence, Manager UI adoption, production acceptance, and Stable qualification remain separate gates.
