#!/usr/bin/env python3
"""Generate clean/release-manifest.json from the current release and the official package.

Phase 0 tool: classifies every file in dev/release as keep / replace / remove.
- keep:   generated, own, or declared official runtime
- replace: path stays, but content must be cleaned in Phase 2 (currently official)
- remove: must not be in the target release
"""
import argparse, hashlib, json, os, datetime

GENERATED = {"HsAuto.exe", "HsAuto.dll", "hdt.dll"}
OFFICIAL_RUNTIME_PREFIX = ("BepInEx.Runtime/",)
OFFICIAL_RUNTIME_EXACT = {"hdt_v3.dll", "Data/hdt-by-id.json"}
OWN = {
    "READ ME BEFORE USE.txt",
    "Data/client-ui.json",
    "Data/hskeeper-window.json",
}
REPLACE_PREFIX = ("Bai/Web/",)
REPLACE_EXACT = set()
REMOVE_PREFIX = ("tutorial-assets/",)
REMOVE_EXACT = {
    "HsAuto_脚本客户端图文教程.html",
    "HsAuto.Watchdog.exe", "HsAuto.Watchdog.runtimeconfig.json",
    "HsAuto.Updater.exe", "HsAuto.Updater.runtimeconfig.json",
    "HsAuto.PackageInfo.json", "HsAuto.UpdateSource.json",
    "HsAuto.PackageIntegrity.json", "HsAuto.CanonicalPackageIntegrity.json",
    "HsAuto.InstalledPackageIntegrity.json", "HsAuto.RenamedPackageIntegrity.json",
    "HsAuto.WebViewPackageIntegrity.json",
    "hsd.dll", "hsdk.dll", "hsmm.dll", "hswebcompat.dll",
    "Bai/Web/login.html", "Bai/Web/login.js",
    "Bai/Web/assets/heisha-wordmark.png",
    "Data/logs/controller.log",
}
REMOVE_REASON = {
    "HsAuto.Watchdog.exe": "official binary: update URL/RSA/integrity/restore",
    "HsAuto.Updater.exe": "official binary: update channel",
    "HsAuto.PackageInfo.json": "official build metadata",
    "HsAuto.UpdateSource.json": "official Gitee update channel",
    "hsd.dll": "official hdt.dll copy", "hsdk.dll": "official hdt.dll copy",
    "hsmm.dll": "official hdt.dll copy", "hswebcompat.dll": "official hdt_v3.dll copy",
    "Bai/Web/login.html": "official card-key login page",
    "Bai/Web/login.js": "official card-key login logic",
    "Bai/Web/assets/heisha-wordmark.png": "official wordmark",
    "Data/logs/controller.log": "dev runtime log",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(rel):
    if rel in REMOVE_EXACT or rel.startswith(REMOVE_PREFIX):
        return "remove", "remove", REMOVE_REASON.get(rel, "official tutorial/residue")
    if rel in GENERATED:
        return "keep", "generated", ""
    if rel in OWN or rel.startswith("环境安装包/"):
        return "keep", "own", ""
    if rel.startswith(OFFICIAL_RUNTIME_PREFIX) or rel in OFFICIAL_RUNTIME_EXACT:
        return "keep", "official-runtime", "declared official runtime"
    if rel.startswith(REPLACE_PREFIX) or rel in REPLACE_EXACT:
        return "replace", "own", "content must be cleaned in Phase 2"
    # Unknown files default to own keep; review them in Phase 1.
    return "keep", "own", "unclassified; review"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", required=True)
    ap.add_argument("--official", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    release = os.path.abspath(args.release)
    official = os.path.abspath(args.official)
    official_hashes = {}
    for dp, _, fs in os.walk(official):
        for f in fs:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, official).replace(os.sep, "/")
            official_hashes[rel] = sha256(p)

    files = []
    for dp, _, fs in os.walk(release):
        for f in fs:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, release).replace(os.sep, "/")
            action, origin, reason = classify(rel)
            files.append({
                "path": rel,
                "action": action,
                "origin": origin,
                "current_sha256": sha256(p),
                "official_sha256": official_hashes.get(rel),
                "reason": reason,
            })
    files.sort(key=lambda x: x["path"])
    keep = sum(1 for x in files if x["action"] == "keep")
    replace = sum(1 for x in files if x["action"] == "replace")
    remove = sum(1 for x in files if x["action"] == "remove")
    manifest = {
        "schema": 1,
        "generated_at_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_dir": release,
        "official_dir": official,
        "expected_count": keep + replace,
        "counts": {"keep": keep, "replace": replace, "remove": remove},
        "files": files,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("manifest:", args.out)
    print("total=%d keep=%d replace=%d remove=%d expected=%d" %
          (len(files), keep, replace, remove, manifest["expected_count"]))


if __name__ == "__main__":
    main()
