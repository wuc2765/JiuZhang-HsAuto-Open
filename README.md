# JiuZhang-HsAuto — Open Materials

This repository contains the **original, non-derivative materials** produced for
the JiuZhang-HsAuto cleanup project:

- build, packaging and release-verification tooling;
- cleanup and environment documentation;
- replacement brand assets (icons and wordmark).

It does **not** contain the application source. The full client
(`core-src/`, `src/`, `plugin-src/`, the Web UI and the game plugin) is derived
from the proprietary HsAuto 0.9.75 product and third-party components. It is
kept in a private repository because the project does not have redistribution
rights for that code, and a repo-wide MIT license would be misleading. See
[NOTICE.md](NOTICE.md).

## What is public

| Path | Contents |
|---|---|
| `tools/` | Original build, bundle, manifest and release-verification scripts |
| `docs/` | Environment/tooling notes and a cleanup history summary |
| `assets/branding/` | Newly generated replacement icons and wordmark |
| `LICENSE` | MIT for the files listed in [ORIGINAL-WORK.md](ORIGINAL-WORK.md) |

## What is private

The private source tree contains the actual client, strategies, plugin,
official-derived UI assets, reference assemblies, official runtime package and
game integrations. Those materials are not published here and are not covered
by this repository's MIT license. Hearthstone, Battle.net, NetEase HSAng and
HsAuto are proprietary products of their respective owners.

## Environment

The public tooling needs Windows, PowerShell 5.1+, Python 3.10+ and (for the
private tree) .NET 8 SDK. See [docs/TOOLING.md](docs/TOOLING.md) for the full
environment and build layout. This repository alone is not a runnable client
and cannot build the private application without the private source and
user-supplied game/BepInEx reference assemblies.

## Safety and legal

This project is not affiliated with NetEase, Blizzard or the HsAuto authors.
Game automation can violate service terms and lead to account bans. The
original materials are provided "as is", without warranty. Do not use them to
redistribute proprietary HsAuto, Hearthstone, Battle.net or HSAng code or
assets.

## License

MIT applies only to the original files enumerated in
[ORIGINAL-WORK.md](ORIGINAL-WORK.md). See [LICENSE](LICENSE) and
[NOTICE.md](NOTICE.md).
