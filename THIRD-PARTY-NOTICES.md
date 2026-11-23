# Third-party notices

This public repository does **not** distribute third-party binaries. The
tooling is written in Python and PowerShell and is intended to operate on a
private source tree supplied by the maintainer.

The private tree references or interoperates with the following components;
they are not included here and remain under their own licenses:

| Component | Role | Note |
|---|---|---|
| HsAuto 0.9.75 | Upstream product from which the private tree is derived | Proprietary; no redistribution rights granted by this project |
| Hearthstone / Battle.net | Game client and services | Proprietary Blizzard Entertainment; assemblies are not distributed |
| NetEase HSAng | Optional Box/AI auth integration | Proprietary NetEase component; not distributed |
| BepInEx / Harmony / MonoMod / Doorstop | Game plugin runtime | Not distributed; see upstream LGPL/MIT terms |
| Microsoft Edge WebView2 | Embedded browser UI | Not distributed; Microsoft terms apply |
| Microsoft.Data.Sqlite / SQLitePCLRaw / SQLite | Local data access | Not distributed; MIT/Apache-2.0/public-domain terms apply |
| zlib 1.2.13 | Compression helper in the private Core build | Not included in this public repository; zlib license applies to the private binary |

## Trademarks

Hearthstone, Battle.net, Blizzard, NetEase, HSAng and other names are
trademarks or registered trademarks of their respective owners. They are used
descriptively for interoperability and research; no endorsement or affiliation
is implied.
