# Manager public website

The canonical source for the GoreeCloud Manager public informational website is now:

`GoreeCloud/goreecloud-static-websites/sites/manager`

The public website is not the private Manager application or its operational backend.

## Migration state

The reviewed website source, Glaze UI 2.2.0 Stable consumer lock, build tooling, validation tooling, and CI contract have been copied to `GoreeCloud/goreecloud-static-websites`.

The legacy `website/` source and repository-local website tooling remain here temporarily only while the existing Cloudflare Pages deployment still references this repository. They are migration/deployment compatibility copies, not the long-term canonical source.

Do not delete the legacy website copy until the centralized source has passed validation, Cloudflare Pages has been cut over to `GoreeCloud/goreecloud-static-websites`, and the exact resulting production deployment has been verified. After those gates are complete, the legacy static website source and obsolete website-specific references in this repository must be removed.

## Deployment boundary

- Canonical source repository: `GoreeCloud/goreecloud-static-websites`
- Canonical source path: `sites/manager`
- Current legacy deployment source: `GoreeCloud/goreecloud-manager`
- Current legacy root directory: blank
- Current legacy build command: `python scripts/build_public_site.py`
- Current legacy build output directory: `dist`
- Production branch: `main`
- Public hostname: `https://manage.goreecloud.com/`
- Private Manager application hostname: `https://manager.goreecloud.com/` — reserved for the authenticated private application and not a public-website destination

The public website canonical namespace is `manage.goreecloud.com`. That namespace assignment does not by itself prove DNS, Cloudflare Pages, TLS, exact deployed-revision, or production publication acceptance.

Until public deployment is independently accepted, the source intentionally ships `noindex` metadata and a blocking `robots.txt`.

## Central build contract

The centralized package remains a ground-up consumer of **Glaze UI 2.2.0 Stable**. `sites/manager/glaze.lock.json` pins the Stable tag, promotion commit, and browser CSS Git blobs. Central CI checks out the exact Glaze revision and verifies every copied blob before producing `sites/manager/dist/`.

Canonical central paths:

- `sites/manager/` — reviewed public static source
- `sites/manager/assets/manager-mark.svg` — approved Manager product mark derivative
- `sites/manager/glaze.lock.json` — Glaze UI 2.2.0 Stable consumer lock
- `sites/manager/scripts/build_public_site.py` — isolated static-site builder
- `sites/manager/scripts/validate_public_site.py` — source and built-artifact validator
- `.github/workflows/validate-manager-site.yml` — central exact-revision validation gate

## Public truth boundary

The site may describe current source-backed Manager capabilities and explicit development gates. It must not expose private runtime details, credentials, topology, or private application destinations; represent conceptual graphics as live operational state; or imply that source acceptance is production approval.
