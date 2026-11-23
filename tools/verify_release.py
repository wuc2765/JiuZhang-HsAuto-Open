#!/usr/bin/env python3
"""Verify a release directory against clean/release-manifest.json.

Phase 0 gate:
- exact-set: expected (keep + replace) files must exist, no extra files
- bundle extract: scan embedded HsAuto.dll / HsAuto.Core.dll, not the compressed exe
- dual encoding: UTF-8/ASCII + UTF-16LE
- official hash identity: own/generated/replace files must not equal official bytes
- removed paths must be absent
- frontend/image checks
- optional game directory check for legacy plugin copies

Use --audit to report but exit 0; default strict exits 1 on any violation.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys

BANNED = [
    "hsauto-update-", "hsauto-license-",
    "HSAUTO_LICENSE_CAPABILITY", "HSAUTO_BRIDGE_SECRET", "HSAUTO_LICENSE_CLIENT_ID",
    "LicenseLeaseToken", "LicenseLeaseClaims", "LicenseFeatureFlags", "MachineFingerprint",
    "license-auth.bin", "TokenLogin", "login-credential.bin", "remote-control.bin",
    "炉石黑纱", "heisha", "HSD AI",
    "frida-clr", "HSAng.exe", "lushi.163.com",
    "D:\\MYPROJECT", "HSAUTO_UPDATE_MANIFEST_URLS", "HsAuto.Watchdog",
    "AttackInputMethodCorrection", "SendAttackInputMethod", "attack-input-method-correction",
    "卡密", "续费", "会员",
]
# Optional private token list for local audits (never commit it):
#   HSAUTO_BANNED_TOKENS_FILE=tools/banned-private.txt
_private_banned = os.environ.get("HSAUTO_BANNED_TOKENS_FILE", "")
if _private_banned and os.path.exists(_private_banned):
    with open(_private_banned, encoding="utf-8") as _f:
        BANNED += [line.strip() for line in _f if line.strip() and not line.lstrip().startswith("#")]
FRONTEND_BANNED = [
    "卡密", "续费卡密", "复制卡密", "更换卡密", "刷新卡密状态",
    "page-vip", "license", "vip", "炉石黑纱", "heisha", "HSD AI",
]
BANNED_IMAGES = {
    "Bai/Web/assets/heisha-wordmark.png",
    "tutorial-assets/heisha-wordmark.png",
    "tutorial-assets/049-license.png",
    "tutorial-assets/049-login-cn.png",
    "tutorial-assets/049-login-global.png",
    "tutorial-assets/049-login-ready.png",
}
# Declared external dependencies (decision 2026-11-23).
# Keep NetEase Box/HSAng; AI3.0 uses the official NetEase Direct prediction API.
# These tokens are allowed only in the named scan targets; anywhere else is a violation.
DECLARED_EXTERNAL = {
    "HSAng.exe": {"bundle/HsAuto.Core.dll", "HsAuto.Core.dll"},
    "lushi.163.com": {"bundle/HsAuto.Core.dll", "HsAuto.Core.dll"},
}
# Decision D8 (2026-11-23): keep Battle.net token persistence, declare it locally.
# The UI store and the Core repair-preserved filename are the only allowed locations.
DECLARED_LOCAL_CREDENTIALS = {
    "TokenLogin": {"bundle/HsAuto.dll", "HsAuto.dll"},
    "login-credential.bin": {
        "bundle/HsAuto.dll", "HsAuto.dll",
        "bundle/HsAuto.Core.dll", "HsAuto.Core.dll",
    },
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_token(data, token):
    return data.count(token.encode("utf-8")) + data.count(token.encode("utf-16le"))


def scan_file(path, tokens, hits, declared, label):
    with open(path, "rb") as f:
        data = f.read()
    for t in tokens:
        n = count_token(data, t)
        if n:
            allowed = DECLARED_EXTERNAL.get(t)
            reason = "declared external dependency"
            if not (allowed and label in allowed):
                allowed = DECLARED_LOCAL_CREDENTIALS.get(t)
                reason = "declared local credential store"
            if allowed and label in allowed:
                declared.append((label, t, n, reason))
            else:
                hits.append((label, t, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--official", required=True)
    ap.add_argument("--python", required=True)
    ap.add_argument("--hsbundle", required=True)
    ap.add_argument("--extract-dir", default="")
    ap.add_argument("--bundle-exe", default="", help="Optional exe whose embedded app assemblies are scanned instead of release/HsAuto.exe")
    ap.add_argument("--game-dir", default="")
    ap.add_argument("--audit", action="store_true")
    args = ap.parse_args()

    release = os.path.abspath(args.release)
    manifest = json.load(open(args.manifest, encoding="utf-8"))
    official = os.path.abspath(args.official)
    violations = []
    warnings = []

    # 1. exact set
    expected = {x["path"]: x for x in manifest["files"] if x["action"] in ("keep", "replace")}
    remove = {x["path"]: x for x in manifest["files"] if x["action"] == "remove"}
    actual = set()
    for dp, _, fs in os.walk(release):
        for f in fs:
            p = os.path.join(dp, f)
            actual.add(os.path.relpath(p, release).replace(os.sep, "/"))
    for p in sorted(expected):
        if p not in actual:
            violations.append(("missing", p))
    for p in sorted(actual - set(expected)):
        action = remove.get(p, {}).get("action", "extra")
        violations.append((action, p))

    # 2. removed paths / official identity
    official_hashes = {}
    for dp, _, fs in os.walk(official):
        for f in fs:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, official).replace(os.sep, "/")
            official_hashes[rel] = sha256(p)
    for p in sorted(actual):
        meta = expected.get(p)
        if not meta:
            continue
        full = os.path.join(release, p)
        if p in BANNED_IMAGES:
            violations.append(("banned-image", p))
        if meta["origin"] in ("own", "generated") and p in official_hashes:
            if sha256(full) == official_hashes[p]:
                violations.append(("official-identical", p))
        if meta["origin"] == "official-runtime" and p in official_hashes:
            if sha256(full) != official_hashes[p]:
                warnings.append(("official-runtime-changed", p))

    # 3. extract bundle and scan binaries
    scan_targets = []
    exe = os.path.abspath(args.bundle_exe) if args.bundle_exe else os.path.join(release, "HsAuto.exe")
    if os.path.exists(exe):
        if args.bundle_exe:
            print("bundle scan exe:", exe)
        extract = args.extract_dir or os.path.join(release, "_verify_bundle")
        if os.path.isdir(extract):
            shutil.rmtree(extract)
        os.makedirs(extract, exist_ok=True)
        r = subprocess.run([args.python, "-I", args.hsbundle, "extract", exe, extract],
                           capture_output=True, text=True)
        if r.returncode != 0:
            violations.append(("bundle-extract-failed", r.stderr.strip()[:200]))
        else:
            for name in ("HsAuto.dll", "HsAuto.Core.dll"):
                p = os.path.join(extract, name)
                if os.path.exists(p):
                    scan_targets.append(("bundle/" + name, p))
                else:
                    violations.append(("bundle-entry-missing", name))
            # Scan every remaining bundle entry, not just the two app assemblies.
            for dp, _, fs in os.walk(extract):
                for f in fs:
                    p = os.path.join(dp, f)
                    rel = os.path.relpath(p, extract).replace(os.sep, "/")
                    if rel in ("HsAuto.dll", "HsAuto.Core.dll"):
                        continue
                    scan_targets.append(("bundle/" + rel, p))
    for name in ("HsAuto.dll", "hdt.dll", "hdt_v3.dll", "HsAuto.Watchdog.exe", "HsAuto.Updater.exe"):
        p = os.path.join(release, name)
        if os.path.exists(p):
            scan_targets.append((name, p))
    # Scan every other release binary (BepInEx runtime, helpers) as well.
    for dp, _, fs in os.walk(release):
        for f in fs:
            if not f.lower().endswith((".dll", ".exe")):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, release).replace(os.sep, "/")
            if rel in {"HsAuto.dll", "hdt.dll", "hdt_v3.dll", "HsAuto.Watchdog.exe", "HsAuto.Updater.exe", "HsAuto.exe"}:
                continue
            scan_targets.append(("release/" + rel, p))

    binary_hits = []
    binary_declared = []
    for label, p in scan_targets:
        scan_file(p, BANNED, binary_hits, binary_declared, label)

    # 4. frontend text scan
    frontend_hits = []
    for rel in ("Bai/Web/index.html", "Bai/Web/app.js", "Bai/Web/login.html", "Bai/Web/login.js",
                "Bai/Web/bai.css", "Bai/Web/design.css", "Bai/Web/bridge.js",
                "HsAuto_脚本客户端图文教程.html", "READ ME BEFORE USE.txt"):
        p = os.path.join(release, rel)
        if not os.path.exists(p):
            continue
        raw = open(p, "rb").read()
        for enc in ("utf-8", "utf-16le"):
            try:
                text = raw.decode(enc, errors="ignore")
            except Exception:
                continue
            for t in FRONTEND_BANNED:
                if t in text:
                    frontend_hits.append((rel, t, text.count(t)))

    # 5. game directory legacy plugin copies
    game_hits = []
    if args.game_dir and os.path.isdir(args.game_dir):
        for sub in ("BepInEx\\plugins", "BepInEx\\patchers"):
            d = os.path.join(args.game_dir, sub)
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if f.lower() in ("hsd.dll", "hsdk.dll", "hsmm.dll", "hswebcompat.dll"):
                    game_hits.append(os.path.join(sub, f))

    def uniq(items):
        seen = set(); out = []
        for x in items:
            if x not in seen:
                seen.add(x); out.append(x)
        return out

    print("release:", release)
    print("expected:", len(expected), "actual:", len(actual))
    print("violations:", len(violations), "warnings:", len(warnings))
    print("binary hits:", len(binary_hits), "declared:", len(binary_declared),
          "frontend hits:", len(frontend_hits), "game hits:", len(game_hits))
    for kind, path in violations:
        print("  VIOLATION", kind, path)
    for kind, path in warnings:
        print("  WARN", kind, path)
    for label, tok, n, reason in binary_declared:
        print("  DECLARED", label, repr(tok), n, "(" + reason + ")")
    for label, tok, n in binary_hits:
        print("  BINARY", label, repr(tok), n)
    for rel, tok, n in frontend_hits:
        print("  FRONTEND", rel, repr(tok), n)
    for p in game_hits:
        print("  GAME", p)

    ok = not (violations or binary_hits or frontend_hits or game_hits)
    if args.audit:
        print("AUDIT MODE: exit 0 (violations reported)")
        return 0
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
