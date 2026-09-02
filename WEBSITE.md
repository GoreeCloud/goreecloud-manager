# Manager public website

GoreeCloud Manager owns a standalone **public informational website** source in this repository. The public website is not the private Manager application or its operational backend.

## Deployment boundary

- Production branch: `main`
- Framework preset: `None`
- Build command: `python scripts/build_public_site.py`
- Build output directory: `dist`
- Root directory: blank
- Public hostname: **not yet approved**

A distinct public namespace must be approved and documented before canonical URL, sitemap, indexing, DNS, or production publication is enabled. The existing private Manager application namespace remains reserved for the private application and must not be repurposed by this website.

Until that public namespace is approved, the source intentionally ships `noindex` metadata and a blocking `robots.txt`.

## Glaze UI baseline

The website is a ground-up consumer of **Glaze UI 2.2.0 Stable**. `website/glaze.lock.json` pins the Stable tag, promotion commit, and each browser CSS Git blob. CI checks out the exact Glaze revision and the build verifies every copied blob before creating `dist/`. Browsers consume only local built assets.

## Source layout

- `website/` — reviewed public source
- `website/assets/manager-mark.svg` — byte-identical consumer derivative of the approved Manager product mark
- `website/glaze.lock.json` — Glaze UI 2.2.0 Stable consumer lock
- `scripts/build_public_site.py` — produces the isolated `dist/` artifact
- `scripts/validate_public_site.py` — validates branding, Glaze provenance, accessibility hooks, private/public separation, indexing gate, security headers, and built-asset integrity
- `.github/workflows/validate-website.yml` — exact-revision website acceptance gate

## Public truth boundary

The site may describe current source-backed Manager capabilities and explicit development gates. It must not expose private runtime details, credentials, topology, or private application destinations; represent conceptual graphics as live operational state; or imply that source acceptance is production approval.
