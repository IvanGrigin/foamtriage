#!/usr/bin/env python3
"""Collect a corpus of REAL OpenFOAM logs from public GitHub repositories.

Code search is rate limited (10 req/min authenticated), so queries are paced.
Downloads go through raw.githubusercontent.com, which needs no auth and is not
rate limited in the same way.

Writes logs to reallogs/ and provenance to reallogs_manifest.json.
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

OUT = "reallogs"
MANIFEST = "reallogs_manifest.json"

# solvers (incl. the .org module runners) and the mesh/utility tools whose
# formats were never confirmed
NAMES = [
    "log.simpleFoam", "log.pimpleFoam", "log.icoFoam", "log.pisoFoam",
    "log.potentialFoam", "log.interFoam", "log.interIsoFoam",
    "log.multiphaseEulerFoam", "log.twoPhaseEulerFoam",
    "log.rhoPimpleFoam", "log.rhoSimpleFoam", "log.sonicFoam",
    "log.buoyantSimpleFoam", "log.buoyantPimpleFoam",
    "log.chtMultiRegionFoam", "log.foamRun", "log.foamMultiRun",
    "log.reactingFoam", "log.XiFoam", "log.sprayFoam", "log.engineFoam",
    "log.scalarTransportFoam", "log.laplacianFoam",
    "log.solidDisplacementFoam", "log.boundaryFoam",
    "log.overPimpleDyMFoam", "log.pimpleDyMFoam",
    "log.blockMesh", "log.checkMesh", "log.snappyHexMesh",
    "log.decomposePar", "log.reconstructPar", "log.setFields",
    "log.topoSet", "log.extrudeMesh", "log.surfaceFeatureExtract",
]

MAX_FILES = 400
MAX_BYTES = 120 * 1024 * 1024
MIN_BYTES = 400


def search(name, page=1):
    cmd = ["gh", "api", "-X", "GET", "search/code",
           "-f", "q=filename:%s" % name, "-f", "per_page=100",
           "-f", "page=%d" % page]
    for attempt in range(4):
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if p.returncode == 0:
            try:
                return json.loads(p.stdout)
            except json.JSONDecodeError:
                return None
        if "rate limit" in (p.stdout + p.stderr).lower():
            wait = 25 * (attempt + 1)
            print("    rate limited, backing off %ds" % wait, flush=True)
            time.sleep(wait)
            continue
        return None
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    seen = set()
    manifest = []
    if os.path.exists(MANIFEST):
        manifest = json.load(open(MANIFEST))
        seen = {(m["repo"], m["path"]) for m in manifest}
        print("resuming with %d already recorded" % len(manifest), flush=True)

    cands = []
    for i, name in enumerate(NAMES, 1):
        d = search(name)
        n = (d or {}).get("total_count", 0)
        items = (d or {}).get("items", []) or []
        print("[%2d/%d] %-30s hits=%-5s fetched=%d"
              % (i, len(NAMES), name, n, len(items)), flush=True)
        for it in items:
            key = (it["repository"]["full_name"], it["path"])
            if key in seen:
                continue
            seen.add(key)
            cands.append({"solver": name.replace("log.", ""),
                          "repo": key[0], "path": key[1]})
        time.sleep(7)          # stay under 10 search req/min

    print("\n%d new candidates\n" % len(cands), flush=True)

    total = sum(m.get("bytes", 0) for m in manifest)
    kept = len([m for m in manifest if m.get("file")])
    for c in cands:
        if kept >= MAX_FILES or total >= MAX_BYTES:
            print("cap reached", flush=True)
            break
        url = "https://raw.githubusercontent.com/%s/HEAD/%s" % (c["repo"], c["path"])
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                data = r.read(8 * 1024 * 1024)
        except Exception as e:
            print("  fail %-60s %s" % ((c["repo"] + "/" + c["path"])[:60], e), flush=True)
            continue
        if len(data) < MIN_BYTES:
            continue
        safe = ("%s__%s__%s" % (c["solver"], c["repo"], c["path"])) \
            .replace("/", "-").replace(" ", "_")[:150]
        fn = os.path.join(OUT, safe + ".log")
        with open(fn, "wb") as fh:
            fh.write(data)
        kept += 1
        total += len(data)
        c["file"] = fn
        c["bytes"] = len(data)
        c["url"] = url
        manifest.append(c)
        if kept % 25 == 0:
            print("  kept %d files, %.1f MB" % (kept, total / 1e6), flush=True)
            json.dump(manifest, open(MANIFEST, "w"), indent=1)

    json.dump(manifest, open(MANIFEST, "w"), indent=1)
    print("\nDONE: %d files, %.1f MB, manifest %s"
          % (kept, total / 1e6, MANIFEST), flush=True)


if __name__ == "__main__":
    main()
