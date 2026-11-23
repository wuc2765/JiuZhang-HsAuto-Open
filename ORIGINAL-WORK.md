# Original work covered by MIT

The following files are original materials authored for the JiuZhang-HsAuto
cleanup and are covered by the root [LICENSE](LICENSE). Anything not listed
here — especially the private application source and any third-party
component — is not covered.

## Tools

| File | Purpose |
|---|---|
| `tools/build-release.ps1` | Assembles the private source tree into a release directory and runs the gate |
| `tools/verify-release.ps1` | Thin wrapper around the Python release verifier |
| `tools/verify_release.py` | Exact-set, binary-token and frontend checks used during cleanup |
| `tools/hsbundle.py` | Bundle inspection/repacking helper used by the build |
| `tools/gen_manifest.py` | Generates the exact-file release manifest |

These scripts are designed for the private source layout. They do not contain
HsAuto application code or game binaries.

## Documentation

- `README.md`
- `NOTICE.md`
- `THIRD-PARTY-NOTICES.md`
- `docs/TOOLING.md`
- `docs/HISTORY.md`
- `ORIGINAL-WORK.md`

The documentation prose is original. It may describe third-party products by
name for interoperability, but does not grant rights to them.

## Brand assets

| File | Provenance |
|---|---|
| `assets/branding/app.ico` | Replacement icon generated for this project |
| `assets/branding/HsAuto.App.Assets.hsauto.ico` | Replacement icon generated for this project |
| `assets/branding/HsAuto.App.Assets.bai-premium.ico` | Replacement icon generated for this project |
| `assets/branding/jiuzhang-wordmark.png` | Replacement wordmark generated for this project |

These images are not the official HsAuto, Blizzard or NetEase logos. Visual
comparison during cleanup confirmed they differ from the official baseline.

## Not covered

The private repository's `core-src/`, `src/`, `plugin-src/`, Web UI HTML/CSS/JS,
official runtime files, reference assemblies, card data and any third-party
library remain under their own terms. They are not part of this public
repository and are not MIT-licensed.
