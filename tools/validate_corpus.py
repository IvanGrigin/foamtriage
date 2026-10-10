#!/usr/bin/env python3
"""Run foamlog over a directory of real logs and flag anything suspicious.

    python3 validate_reallogs.py reallogs/

This is the harness that actually earns trust: synthetic fixtures prove the
structure, real logs prove the wording. It asserts nothing about values it
cannot know — it looks for the shapes that mean "the parser missed something".
"""
import os
import sys

from foamtriage import SOLVED_TOL, FoamLog

BIG = 20000  # bytes: above this a log should have a time loop

#: the run died before OpenFOAM printed anything, so a missing header is the
#: truth about the log rather than a parser miss
from foamtriage._diagnostics import PRE_EXEC_REASONS

PRE_EXEC_FAILURES = PRE_EXEC_REASONS


def check(path):
    size = os.path.getsize(path)
    try:
        log = FoamLog.load(path)
        r = log.summary()
    except Exception as e:
        return None, ["PARSER CRASHED: %s: %s" % (type(e).__name__, e)]
    why = []
    started = r["reason"] not in PRE_EXEC_FAILURES
    if not r["solver"] and started:
        why.append("no solver name")
    if r["solver_source"] == "filename":
        pass  # header was stripped; inferring from the filename is expected
    if not r["version"] and started and r["solver_source"] == "exec":
        why.append("no version")
    if r["fork"] == "unknown" and r["version"]:
        # a log with no banner at all is honestly unknown; only doubt the fork
        # when the header was there and still unidentifiable
        why.append("fork unknown despite a parsed banner")
    if size > BIG and started:
        if r["n_steps"] == 0:
            why.append("big log but no time steps")
        if not r["fields"] and r["n_steps"] == 0:
            why.append("big log with neither steps nor residual fields")
        if r["status"] == "incomplete" and r["n_steps"] == 0:
            # a killed or still-running solver legitimately reports incomplete;
            # only a big log with no time loop at all means a parser miss
            why.append("big log with no time loop reported incomplete")
    if r["status"] == "failed" and r["reason"] in ("fatal_error", "fatal_io_error"):
        why.append("failed but the table could not name the error (reason=%s)" % r["reason"])
    for name, v in r["residuals"].items():
        if v["trend"] == "diverging" and (v["last_final"] or 0) <= SOLVED_TOL:
            why.append("%s called diverging at a converged residual" % name)
    return r, why


def main(argv):
    root = argv[0] if argv else "reallogs"
    if not os.path.isdir(root):
        print("no such directory: %s" % root)
        return 2
    skip = (".md", ".json", ".py", ".csv", ".parquet")
    files = sorted(f for f in os.listdir(root)
                   if not f.startswith(".") and not f.endswith(skip))
    if not files:
        print("no logs in %s" % root)
        return 2

    print("%-42s %-20s %-5s %-7s %6s %-28s" %
          ("file", "solver", "fork", "ver", "steps", "status/reason"))
    print("-" * 114)
    flagged = []
    for f in files:
        path = os.path.join(root, f)
        r, why = check(path)
        if r is None:
            print("%-42s %s" % (f[:42], why[0]))
            flagged.append((f, why))
            continue
        print("%-42s %-20s %-5s %-7s %6d %-28s" %
              (f[:42], (r["solver"] or "''")[:20], r["fork"],
               (r["version"] or "''")[:7], r["n_steps"],
               (r["status"] + "/" + r["reason"])[:28]))
        if why:
            flagged.append((f, why))

    print()
    if flagged:
        print("SUSPECT (%d/%d):" % (len(flagged), len(files)))
        for f, why in flagged:
            for w in why:
                print("  %-44s %s" % (f[:44], w))
        return 1
    print("clean: %d real logs, nothing suspicious" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
