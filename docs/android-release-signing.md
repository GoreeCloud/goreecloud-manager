# Android Release Signing

## Purpose

I use this document to define the GoreeCloud Manager Android release-signing boundary. Source validation, unsigned release packaging, production signing, and real-device acceptance are separate stages. A successful CI build does not by itself make an Android package a production or Stable release.

## Package states

GoreeCloud Manager currently produces two Android acceptance artifacts through the Client packaging workflow:

- `app-debug.apk` — debug acceptance package for development and device testing.
- `app-release-unsigned.apk` — non-debuggable release-variant package that is intentionally unsigned and cannot be treated as a production installable release.

The production-signed APK is created only after an approved signing identity is available outside the repository and an administrator explicitly performs the signing operation in a trusted environment.

## Signing identity boundary

I do not store an Android signing keystore, keystore password, key password, signing private key, or equivalent reusable signing material in Git, GitHub Actions workflow files, build scripts, documentation, or release artifacts.

The repository `.gitignore` excludes common Android signing-container extensions as an additional local safety boundary. This does not replace secure credential storage or administrative review.

The signing helper requires these environment variables at execution time:

- `ANDROID_KEYSTORE_FILE` — local path to the approved external keystore.
- `ANDROID_KEYSTORE_PASSWORD` — keystore password.
- `ANDROID_KEY_ALIAS` — approved signing-key alias.
- `ANDROID_KEY_PASSWORD` — signing-key password.

The passwords are passed to Android SDK `apksigner` through environment-variable password sources rather than literal command-line password values.

## Signing procedure

Before signing, I verify that:

1. The source revision is the accepted release candidate.
2. Client packaging passed on that exact revision.
3. The unsigned release APK checksum matches the retained CI evidence.
4. The signing system is trusted and has the approved Android SDK `apksigner` tool.
5. The approved keystore remains outside the repository and is available only for the controlled signing operation.

I then set the required environment variables in the trusted administrative environment and run:

```bash
bash android-client/scripts/sign-release-apk.sh \
  path/to/app-release-unsigned.apk \
  path/to/goreecloud-manager-release.apk
```

The helper fails closed when required inputs are absent, refuses to sign in place, refuses to overwrite existing signed/evidence outputs, signs with the external keystore, runs `apksigner verify --verbose --print-certs`, and records both a SHA-256 checksum and public signature-verification evidence.

## Acceptance after signing

A cryptographically valid signature is necessary but not sufficient for release acceptance. Before I classify the Android client as Stable or production accepted, I must also:

- compare the reported signing-certificate fingerprint with the approved GoreeCloud Android signing identity record;
- install the exact signed APK on an approved physical Android device;
- verify launch, authentication, HTTPS-only navigation, TLS failure handling, external-navigation rejection, loading/error/retry behavior, application identity, and representative Glaze UI behavior;
- verify that the signed application retains the intended `com.goreecloud.manager` production application ID rather than the debug application ID;
- record the exact source revision, unsigned artifact checksum, signed artifact checksum, certificate fingerprint evidence, device acceptance result, and release classification without recording private signing material.

## GitHub Actions boundary

I do not add an automatically usable production-signing workflow until the repository has an explicitly protected signing environment with appropriate approval controls and externally stored signing secrets. Referencing an unprotected or automatically created environment would weaken the approval boundary. Until that protection exists, CI stops at the unsigned release artifact and the repository-owned signing helper provides the controlled handoff.

## Rollback and recovery

The unsigned release artifact contains no signing secret. Removing the unsigned artifact or reverting the source changes requires no signing-key rollback. If a signing identity is suspected of compromise, I stop release signing, preserve evidence, and follow the separate credential/key-recovery process rather than modifying repository history to conceal the event.
