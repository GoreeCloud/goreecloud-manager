## Purpose

<!-- What problem does this change solve, and why is it needed now? -->

## Changes

<!-- Summarize the focused implementation. -->

## Glaze UI impact

- [ ] No user-interface change
- [ ] Glaze UI behavior/visuals changed and applicable accessibility/privacy contracts were reviewed

<!-- If UI changed, describe hierarchy, focus/keyboard behavior, practical target sizing, appearance/contrast behavior, reduced motion, and local asset/dependency handling. -->

## Security and privacy boundary

- [ ] Manager remains read-only
- [ ] No reusable secret, credential, private key, production configuration, personal data, or sensitive log output is included
- [ ] Error/log output remains sanitized
- [ ] No unapproved infrastructure mutation or production activation is introduced

<!-- Explain any security-sensitive behavior or boundary change. -->

## Validation

- [ ] Relevant local/static tests pass
- [ ] CI
- [ ] Runtime Publication Readiness
- [ ] Backup Restore Readiness
- [ ] Upgrade Rollback Readiness
- [ ] Monitoring Alert Readiness
- [ ] Production Readiness Evidence Manifest

<!-- Record the exact final head and relevant run/evidence identifiers when available. -->

## Documentation and recovery

- [ ] Code-adjacent documentation is updated when behavior, structure, configuration, security, or recovery expectations changed
- [ ] Rollback/recovery impact is understood and documented

## Production boundary

<!-- State explicitly whether any production Docker state, deployment, credential, secret, DNS, Caddy, NetBird, firewall, monitor, notification route, backup repository, application data, or activation changed. Source-only work should say that production remains separately approval-controlled. -->

## Known limitations / follow-up

<!-- Record remaining work without claiming it is complete. -->
