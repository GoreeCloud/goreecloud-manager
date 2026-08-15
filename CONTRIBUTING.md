# Contributing to GoreeCloud Manager

GoreeCloud Manager is a privacy-first, read-only administration and operations console for GoreeCloud. Contributions must preserve that operating boundary, the Glaze UI design language, source-control integrity, and GoreeCloud's security and recovery requirements.

## Before changing code

- Keep production activation separate from source development. A merged source change does not approve deployment.
- Preserve Manager's read-only authority unless an explicit approved project decision changes that boundary.
- Do not add passwords, tokens, private keys, populated environment files, production configuration, personal data, or other reusable secrets to Git history, pull requests, logs, screenshots, fixtures, or documentation.
- Prefer local and self-hosted dependencies. Browser-facing UI assets must remain local unless a documented exception is approved.
- Keep the Google Drive `GoreeCloud — Project Specification — Manager` as the governing project record. Repository documentation is an implementation companion, not a competing authority.

## Glaze UI requirements

All user-facing changes must follow the GoreeCloud Glaze UI design language. Preserve clear hierarchy, layered surfaces, practical target sizes, keyboard focus visibility, reduced-motion-safe behavior, high-contrast/forced-colors operability, privacy-first browser behavior, and local GoreeCloud identity assets.

Desktop and web implementations may use platform-appropriate controls, but they should remain visually and behaviorally consistent with the same Glaze UI principles.

## Security and privacy requirements

- Fail closed for malformed security-sensitive configuration.
- Sanitize operational errors before presenting or logging them; do not expose credentials, query strings, filesystem secrets, raw upstream bodies, or unnecessary caller metadata.
- Keep credentials outside source files. Use approved protected-file or environment references where integration credentials are required.
- Preserve strict SSH host-identity verification for the Linux desktop client.
- Do not introduce Docker, NetBird, systemd, firewall, DNS, Caddy, backup, or other infrastructure mutations into the read-only Manager client without explicit authorization and corresponding governance updates.

## Validation

Run the relevant local tests before opening a pull request. Repository changes are accepted only after the exact pull-request head passes all six permanent Manager readiness workflows:

1. CI
2. Runtime Publication Readiness
3. Backup Restore Readiness
4. Upgrade Rollback Readiness
5. Monitoring Alert Readiness
6. Production Readiness Evidence Manifest

Do not waive or bypass a failed gate merely to merge a change. Correct the underlying implementation, test, evidence, or documented policy issue first.

For Glaze UI changes, automated checks are regression evidence rather than a substitute for final authenticated visual and accessibility review in representative browsers, widths, appearance modes, and supported desktop environments.

## Pull-request workflow

- Start from the current `main` branch and keep each pull request focused on one coherent increment.
- Use draft pull requests while implementation or exact-head validation is incomplete.
- Document the purpose, affected boundary, validation performed, known limitations, and production impact.
- Preserve the explicit production boundary. If no production resource changed, say so.
- Merge only after the final reviewed head is green. Revalidate the resulting `main` revision when the change affects release-readiness contracts.

## Documentation

Update code-adjacent documentation when behavior, structure, configuration, security boundaries, recovery expectations, or validation contracts change. Do not duplicate authoritative information unnecessarily; link or summarize the governing record instead.
