# GoreeCloud Manager Android Client

The Android client is a minimal, GoreeCloud-owned application shell for the private GoreeCloud Manager web interface at `https://manager.goreecloud.com/`.

## Security boundary

The client is intentionally narrow. It does not add infrastructure mutation authority, a JavaScript bridge, cleartext networking, custom certificate bypasses, third-party cookies, file access, content-provider access, or arbitrary external navigation. TLS errors fail closed. Main-frame failures surface a Wardveil Security degraded state with an explicit retry action.

The embedded browser is restricted to HTTPS navigation on `manager.goreecloud.com`. The application relies on the existing Manager authentication and authorization controls rather than duplicating credentials in Android-native storage.

## Glaze UI

The application shell uses a restrained native surface while the canonical Manager experience remains the Glaze UI 1.1 web interface. Native loading, failure, and recovery states must remain consistent with GoreeCloud Glaze UI and Wardveil Security conventions.

## Build

CI builds a debug acceptance APK through `.github/workflows/client-packaging.yml`. Production release signing is intentionally separate from source validation and must use an approved GoreeCloud signing key stored outside the repository.
