# Security Policy

## Supported security state

GoreeCloud Manager is under active development. Security fixes are applied to the current `main` source line and validated through the repository's permanent readiness workflows. A source revision, release artifact, or passing CI run must not be interpreted as production approval unless the separate GoreeCloud target-environment readiness process explicitly records that approval.

## Reporting a vulnerability

Please do not publish active credentials, tokens, private keys, personal information, production configuration, internal network details, or a working exploit containing sensitive GoreeCloud data in a public issue or pull request.

For a suspected vulnerability that can be described safely without reusable secrets or private data, open a GitHub issue with the minimum information needed to reproduce and assess the problem. Mark the report clearly as a security concern and use synthetic values wherever possible.

If safe public disclosure is not possible, do not place the sensitive material in repository history. Use GitHub's private vulnerability-reporting capability when it is enabled for this repository, or contact the repository owner through an approved private channel listed on the GoreeCloud profile.

## What to include

A useful report identifies the affected component and revision, the security boundary that fails, the expected behavior, the observed behavior, and a minimal reproduction using synthetic data. Include logs only after removing credentials, tokens, query strings, personal information, internal secret paths, and other unnecessary sensitive values.

## Security boundaries to preserve

GoreeCloud Manager is designed around least privilege and read-only operational visibility. Reports are especially important when they involve authentication or session handling, secret or credential exposure, cross-user data access, unsafe browser behavior, SSH host-identity handling, command injection, unapproved infrastructure mutation, dependency or image integrity, backup/restore integrity, release-provenance integrity, or a bypass of required readiness gates.

## Response and remediation

Security findings are reviewed before unrelated feature expansion when they can affect confidentiality, integrity, authentication, authorization, recoverability, or release evidence. Remediation should include regression coverage and applicable readiness validation. A failed security gate is corrected rather than waived simply to make a pull request mergeable.

No production deployment, credential rotation, firewall change, DNS change, Caddy change, NetBird change, backup operation, or other live infrastructure action is authorized by this policy itself.
