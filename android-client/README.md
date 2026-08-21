# GoreeCloud Manager Android Client

The Android client is a minimal, GoreeCloud-owned application shell for the private GoreeCloud Manager web interface at `https://manager.goreecloud.com/`.

## Security boundary

The client is intentionally narrow. It does not add infrastructure mutation authority, a JavaScript bridge, cleartext networking, custom certificate bypasses, third-party cookies, file access, content-provider access, or arbitrary external navigation. TLS errors fail closed. Main-frame failures surface a Wardveil Security degraded state with an explicit retry action.

The embedded browser is restricted to HTTPS navigation on `manager.goreecloud.com`. The application relies on the existing Manager authentication and authorization controls rather than duplicating credentials in Android-native storage.

## Glaze UI

The application shell uses a restrained native surface while the canonical Manager experience remains the Glaze UI web interface. Native loading, failure, and recovery states must remain consistent with GoreeCloud Glaze UI and Wardveil Security conventions.

## Build and release boundary

The Client packaging workflow builds two Android acceptance variants from the exact source revision:

- a debug acceptance APK for development and physical-device testing;
- an unsigned, non-debuggable release APK for release-path validation and controlled signing handoff.

Production release signing is intentionally separate from CI source/package validation. An approved GoreeCloud signing keystore and its passwords must remain outside the repository. The repository-owned `scripts/sign-release-apk.sh` helper signs an accepted unsigned release artifact with Android SDK `apksigner`, verifies the resulting signature, and records checksum/signature evidence without embedding signing material in source control.

A signed APK still requires physical-device acceptance before any Stable or production-client classification. See `../docs/android-release-signing.md` for the complete signing and acceptance contract.
