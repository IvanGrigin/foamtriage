"""Command line interface.

Every command prints JSON on stdout and nothing else, so the caller never has
to parse prose. Errors are JSON too, with a ``fix`` field: no tracebacks.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from . import __version__
from ._log import FoamLog, Status

if TYPE_CHECKING:
    from pathlib import Path

#: Exit codes, so a caller can branch without reading stdout.
EXIT_OK = 0
EXIT_RUN_PROBLEM = 1
EXIT_USAGE = 2

STEP_COLUMNS = (
    "time",
    "delta_t",
    "courant_max",
    "interface_courant_max",
    "exec_time",
    "clock_time",
    "n_solves",
)

CAPABILITIES: dict[str, Any] = {
    "tool": "foamtriage",
    "version": __version__,
    "purpose": (
        "Turn an OpenFOAM log of any size into a verdict that fits in a couple "
        "of hundred tokens, with drill-down on request."
    ),
    "contract": {
        "summary_max_bytes": 2048,
        "summary_is_flat_in_run_length": True,
        "never_returns_file_contents": True,
        "all_output_is_json_on_stdout": True,
    },
    "exit_codes": {
        str(EXIT_OK): "parsed; run healthy",
        str(EXIT_RUN_PROBLEM): "parsed; run failed, diverged or finished dirty",
        str(EXIT_USAGE): "bad arguments or unreadable file",
    },
    "commands": {
        "parse": {
            "args": ["LOG"],
            "returns": "the capped summary object",
            "typical_bytes": "800-2000",
            "use_when": "first look; answers status, why, and what to change",
        },
        "diagnose": {
            "args": ["LOG"],
            "returns": "kind, status, reason, full diagnostics with prose, fix",
            "use_when": "the summary said something failed and you want the cause",
        },
        "residuals": {
            "args": ["LOG", "--field F", "--last N"],
            "returns": "one row per time step for field F",
            "typical_bytes": "~75 per row",
            "use_when": "you need the shape of a convergence history",
        },
        "steps": {
            "args": ["LOG", "--out PATH", "--format auto|csv|parquet"],
            "returns": "{format, rows, path}; the table goes to PATH, not stdout",
            "use_when": "something else will plot or aggregate the per-step table",
        },
        "capabilities": {"args": [], "returns": "this object"},
    },
    "known_limits": [
        (
            "trend verdicts use a 1e-6 absolute tolerance plus ratio tests; "
            "tuned against 364 real logs, not derived from solver tolerances"
        ),
        (
            "the diagnostics table names 37 failure modes; anything else falls "
            "back to reason=fatal_error with the raw log untouched"
        ),
        (
            "utility logs (blockMesh, checkMesh, snappyHexMesh) are recognised "
            "by Exec name but their contents are not parsed"
        ),
        "snappyHexMesh failure strings are a deliberate gap, not an oversight",
    ],
}


def exit_code(log: FoamLog) -> int:
    """Branchable verdict, so stdout need not be read to know the outcome."""
    if log.status in {Status.FAILED, Status.DIVERGED} or log.diverging:
        return EXIT_RUN_PROBLEM
    return EXIT_OK


def write_steps(log: FoamLog, path: str | Path, fmt: str = "auto") -> dict[str, Any]:
    """Write the per-step table. ``auto`` picks Parquet when the path ends in
    ``.parquet`` and pyarrow is importable, otherwise CSV."""
    rows = [{c: getattr(s, c) for c in STEP_COLUMNS} for s in log.steps]
    want_parquet = fmt == "parquet" or (
        fmt == "auto" and str(path).endswith(".parquet")
    )
    if want_parquet:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            if fmt == "parquet":
                msg = (
                    "parquet requested but pyarrow is not installed; "
                    "use --format csv or pip install 'foamtriage[parquet]'"
                )
                raise RuntimeError(msg) from None
        else:
            table = pa.table({c: [r[c] for r in rows] for c in STEP_COLUMNS})
            pq.write_table(table, path)
            return {"format": "parquet", "rows": len(rows), "path": str(path)}

    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(STEP_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return {"format": "csv", "rows": len(rows), "path": str(path)}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="foamtriage",
        description="Summarise an OpenFOAM log into a verdict.",
    )
    ap.add_argument("--version", action="version", version=f"foamtriage {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="print the capped summary as JSON")
    p.add_argument("log")

    p = sub.add_parser("diagnose", help="status, named failures and the fix")
    p.add_argument("log")

    p = sub.add_parser("residuals", help="per-step residuals for one field")
    p.add_argument("log")
    p.add_argument("--field", required=True)
    p.add_argument("--last", type=int, default=None)

    p = sub.add_parser("steps", help="write the per-step table to a file")
    p.add_argument("log")
    p.add_argument("--out", required=True)
    p.add_argument("--format", choices=("auto", "csv", "parquet"), default="auto")

    sub.add_parser("capabilities", help="machine-readable description of this tool")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "capabilities":
        print(json.dumps(CAPABILITIES, indent=1))
        return EXIT_OK

    try:
        if args.cmd == "parse":
            log = FoamLog.load(args.log)
            print(json.dumps(log.summary()))
            return exit_code(log)
        if args.cmd == "diagnose":
            log = FoamLog.load(args.log)
            print(
                json.dumps(
                    {
                        "kind": log.kind.value,
                        "status": log.status.value,
                        "reason": log.reason,
                        "diagnostics": [
                            {
                                "id": d.id,
                                "severity": d.severity.value,
                                "cause": d.cause,
                                "fix_note": d.fix_note,
                                "detail": dict(d.detail),
                                "first_line": d.first_line,
                                "count": d.count,
                            }
                            for d in log.diagnostics
                        ],
                        "fix": dict(log.fix),
                    }
                )
            )
            return exit_code(log)
        if args.cmd == "residuals":
            rows = FoamLog.load(args.log).residual_history(args.field, last=args.last)
            print(
                json.dumps(
                    [
                        {
                            "time": r.time,
                            "initial": r.initial,
                            "final": r.final,
                            "iterations": r.iterations,
                        }
                        for r in rows
                    ]
                )
            )
            return EXIT_OK
        if args.cmd == "steps":
            log = FoamLog.load(args.log)
            print(json.dumps(write_steps(log, args.out, args.format)))
            return EXIT_OK
    except OSError as e:
        # errors are data too: nobody should have to parse a traceback
        print(
            json.dumps(
                {
                    "error": "io_error",
                    "detail": str(e),
                    "fix": {"note": "check the path and read permissions"},
                }
            )
        )
        return EXIT_USAGE
    except RuntimeError as e:
        print(json.dumps({"error": "runtime_error", "detail": str(e)}))
        return EXIT_USAGE
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
