#!/usr/bin/env python3
"""Run foamtriage over a directory of real logs and flag anything suspicious.

    python3 tools/validate_corpus.py /path/to/logs

Synthetic fixtures prove the structure; only real logs prove the wording. This
asserts nothing about values it cannot know — it looks for the shapes that mean
the parser missed something.
"""

from __future__ import annotations

import sys
from pathlib import Path

from foamtriage import SOLVED_TOL, FoamLog, Kind, Status, Trend
from foamtriage._diagnostics import PRE_EXEC_REASONS

#: Above this, a solver log should have a time loop.
BIG = 20_000

SKIP_SUFFIXES = (".md", ".json", ".py", ".csv", ".parquet")


def check(path: Path) -> tuple[FoamLog | None, list[str]]:
    """Return the parsed log and the reasons to doubt it."""
    try:
        log = FoamLog.read(path)
    except Exception as exc:  # noqa: BLE001 - a crash IS the finding here
        return None, [f"PARSER CRASHED: {type(exc).__name__}: {exc}"]

    why: list[str] = []
    # A run that died before OpenFOAM printed anything has no header to parse,
    # which is the truth about the log rather than a parser miss.
    started = log.reason not in PRE_EXEC_REASONS

    if not log.solver and started:
        why.append("no solver name")
    if not log.version and started and log.solver_source.value == "exec":
        why.append("no version")
    if log.fork == "unknown" and log.version:
        why.append("fork unknown despite a parsed banner")

    # blockMesh, checkMesh and friends never have a time loop
    if path.stat().st_size > BIG and started and log.kind is not Kind.UTILITY:
        if log.n_steps == 0:
            why.append("big log with no time steps")
        if not log.fields and log.n_steps == 0:
            why.append("big log with neither steps nor residual fields")
        if log.status is Status.INCOMPLETE and log.n_steps == 0:
            why.append("big log with no time loop reported incomplete")

    if log.status is Status.FAILED and log.reason in {"fatal_error", "fatal_io_error"}:
        why.append(f"failed but the table could not name it (reason={log.reason})")

    for name, hist in log.residuals.items():
        if hist.trend is Trend.DIVERGING and (hist.last_final or 0.0) <= SOLVED_TOL:
            why.append(f"{name} called diverging at a converged residual")

    return log, why


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else Path("reallogs")
    if not root.is_dir():
        print(f"no such directory: {root}")
        return 2

    files = sorted(
        p
        for p in root.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix not in SKIP_SUFFIXES
    )
    if not files:
        print(f"no logs in {root}")
        return 2

    header = (
        f"{'file':42} {'solver':20} {'fork':5} {'ver':7} {'steps':>6} status/reason"
    )
    print(header)
    print("-" * len(header))

    flagged: list[tuple[str, list[str]]] = []
    for path in files:
        log, why = check(path)
        if log is None:
            print(f"{path.name[:42]:42} {why[0]}")
            flagged.append((path.name, why))
            continue
        print(
            f"{path.name[:42]:42} {log.solver[:20]:20} {log.fork:5} "
            f"{log.version[:7]:7} {log.n_steps:6d} "
            f"{log.status.value}/{log.reason}"
        )
        if why:
            flagged.append((path.name, why))

    print()
    if flagged:
        print(f"SUSPECT ({len(flagged)}/{len(files)}):")
        for name, reasons in flagged:
            for reason in reasons:
                print(f"  {name[:44]:44} {reason}")
        return 1
    print(f"clean: {len(files)} real logs, nothing suspicious")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
