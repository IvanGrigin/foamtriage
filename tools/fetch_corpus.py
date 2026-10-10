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
    "log.simpleFoam",
    "log.pimpleFoam",
    "log.icoFoam",
    "log.pisoFoam",
    "log.potentialFoam",
    "log.interFoam",
    "log.interIsoFoam",
    "log.multiphaseEulerFoam",
    "log.twoPhaseEulerFoam",
    "log.rhoPimpleFoam",
    "log.rhoSimpleFoam",
    "log.sonicFoam",
    "log.buoyantSimpleFoam",
    "log.buoyantPimpleFoam",
    "log.chtMultiRegionFoam",
    "log.foamRun",
    "log.foamMultiRun",
    "log.reactingFoam",
    "log.XiFoam",
    "log.sprayFoam",
    "log.engineFoam",
    "log.scalarTransportFoam",
    "log.laplacianFoam",
    "log.solidDisplacementFoam",
    "log.boundaryFoam",
    "log.overPimpleDyMFoam",
    "log.pimpleDyMFoam",
    "log.blockMesh",
    "log.checkMesh",
    "log.snappyHexMesh",
    "log.decomposePar",
    "log.reconstructPar",
    "log.setFields",
    "log.topoSet",
    "log.extrudeMesh",
    "log.surfaceFeatureExtract",
]

MAX_FILES = 400
MAX_BYTES = 120 * 1024 * 1024
MIN_BYTES = 400


def search(name, page=1):
    cmd = [
        "gh",
        "api",
        "-X",
        "GET",
        "search/code",
        "-f",
        f"q=filename:{name}",
        "-f",
        "per_page=100",
        "-f",
        f"page={page}",
    ]
    for attempt in range(4):
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
        if p.returncode == 0:
            try:
                return json.loads(p.stdout)
            except json.JSONDecodeError:
                return None
        if "rate limit" in (p.stdout + p.stderr).lower():
            wait = 25 * (attempt + 1)
            print(f"    rate limited, backing off {wait}s", flush=True)
            time.sleep(wait)
            continue
        return None
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    seen = set()
    manifest = []
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as fh:
            manifest = json.load(fh)
        seen = {(m["repo"], m["path"]) for m in manifest}
        print(f"resuming with {len(manifest)} already recorded", flush=True)

    cands = []
    for i, name in enumerate(NAMES, 1):
        d = search(name)
        n = (d or {}).get("total_count", 0)
        items = (d or {}).get("items", []) or []
        print(
            f"[{i:2d}/{len(NAMES)}] {name:<30} hits={n:<5} fetched={len(items)}",
            flush=True,
        )
        for it in items:
            key = (it["repository"]["full_name"], it["path"])
            if key in seen:
                continue
            seen.add(key)
            cands.append(
                {"solver": name.replace("log.", ""), "repo": key[0], "path": key[1]}
            )
        time.sleep(7)  # stay under 10 search req/min

    print(f"\n{len(cands)} new candidates\n", flush=True)

    total = sum(m.get("bytes", 0) for m in manifest)
    kept = len([m for m in manifest if m.get("file")])
    for c in cands:
        if kept >= MAX_FILES or total >= MAX_BYTES:
            print("cap reached", flush=True)
            break
        url = f"https://raw.githubusercontent.com/{c['repo']}/HEAD/{c['path']}"
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                data = r.read(8 * 1024 * 1024)
        except (OSError, ValueError) as e:
            # a URL with spaces or non-ascii, a 404, a timeout: skip and go on
            target = f"{c['repo']}/{c['path']}"[:60]
            print(f"  fail {target:<60} {e}", flush=True)
            continue
        if len(data) < MIN_BYTES:
            continue
        safe = f"{c['solver']}__{c['repo']}__{c['path']}".replace("/", "-").replace(
            " ", "_"
        )[:150]
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
            print(f"  kept {kept} files, {total / 1e6:.1f} MB", flush=True)
            with open(MANIFEST, "w") as fh:
                json.dump(manifest, fh, indent=1)

    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(
        f"\nDONE: {kept} files, {total / 1e6:.1f} MB, manifest {MANIFEST}", flush=True
    )


if __name__ == "__main__":
    main()
