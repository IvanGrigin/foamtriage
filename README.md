# foamtriage

[![CI](https://github.com/IvanGrigin/foamtriage/actions/workflows/ci.yml/badge.svg)](https://github.com/IvanGrigin/foamtriage/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue)](https://github.com/IvanGrigin/foamtriage)
[![Licence](https://img.shields.io/badge/licence-MIT-green)](LICENSE)

Turn an OpenFOAM log into a verdict that fits in a few hundred tokens.

```
10 000-step log   10 648 456 bytes
its summary            1 200 bytes      8 874× smaller, in 0.32 s
```

The summary does not grow with the run: six steps and ten thousand steps both
produce about a kilobyte. That is the point — a solver log is sized for a disk,
not for a terminal, a dashboard or a model's context window.

```bash
pip install foamtriage
```

No runtime dependencies. It installs on a cluster login node with nothing but a
stdlib Python 3.10.

## Use

```bash
foamtriage parse log.simpleFoam      # the verdict
echo $?                              # 0 healthy, 1 run problem, 2 unreadable
foamtriage diagnose log.simpleFoam   # the named cause and what to change
foamtriage residuals log.X --field p --last 50
foamtriage steps log.X --out steps.parquet
```

```python
from foamtriage import FoamLog, Status

log = FoamLog.load("log.simpleFoam")
if not log.healthy:
    print(log.reason, log.fix["note"])
```

A run that crashed after the time step grew too large:

```json
{"status": "failed", "reason": "fp_exception", "n_steps": 6,
 "courant_max": 41182.0, "diverging": ["Ux", "Uy", "p", "epsilon", "k"],
 "fix": {"adjustTimeStep": true, "maxCo": 0.9,
         "note": "Courant number reached 41182 before the crash; limit the time step"}}
```

A missing boundary condition, named with the offending patch:

```json
{"status": "failed", "reason": "missing_patch_field",
 "diagnostics": [{"id": "missing_patch_field", "detail": {"patch": "outlet"}}],
 "fix": {"note": "add a boundaryField entry for patch outlet in the field file named by the error"}}
```

## What it is not

OpenFOAM ships `bin/foamLog`, which extracts plottable xy columns from a log for
a human to graph. Its per-step output overlaps with what `foamtriage` exposes as
`residuals` and `steps`, and if plotting is what you want, use it.

What `foamLog` does not do is **name a failure**. `foamtriage` carries a table
of 56 recognised failure modes, each with the specifics pulled out of the
message and one action to take.

Each entry records where it came from. 43 of the 56 have been seen firing on
real logs (`source=corpus`); the other 13 are plausible but unobserved
(`source=inferred`), and a hit on one of those is a hint rather than a verdict.
If you get one, the log is worth an issue.

## Careful about one thing

`status` answers *did the executable finish*, not *is the answer any good*.
A run that reaches `End` with a runaway residual reports:

```
status  completed
reason  end_reached_with_divergence
```

The names in `diverging` survive the summary's caps for exactly this reason.

## Validated against real logs

Developed against a corpus of **884 real logs** from public repositories — 364
solver logs and 520 from the meshing and decomposition utilities — which found
bugs no synthetic fixture would have:

- `Time = 1s` — openfoam.org v11+ appends a unit, so a regex anchored on the
  number reports one step for an entire run.
- `Web:` instead of `Website:` on builds up to ~v5, and the domain written
  `www.OpenFOAM.org`: 34 logs with an unidentifiable fork.
- `foamRun` with **no** `-solver` argument in 3 of 5 real logs; the module then
  comes from `controlDict` and only `Selecting solver` reveals it.
- `foamMultiRun` names one module per region, so the last is not the run.
- Capitalised `Cannot find file`, and `Entry 'X' not found in dictionary "Y"` —
  the most common unnamed failure, 20 of 364.
- A 64-rank job repeats its preamble per rank, so the banner can be a thousand
  lines down.
- Five forks in the wild: openfoam.org, openfoam.com, foam-extend, RapidCFD, and
  logs with no banner at all.

The corpus is not redistributed (mixed licences, 104 repositories); each finding
is pinned as a minimal log in the tests instead.

## Limits, stated plainly

- Trend verdicts use a 1e-6 absolute tolerance plus ratio tests. Tuned against
  real logs, not derived from solver tolerances.
- The table names 37 failure modes. Anything else reports `fatal_error` and
  leaves the log untouched — then read its tail, not the whole file.
- Utility logs (`blockMesh`, `checkMesh`, `snappyHexMesh`, `decomposePar`) have
  their failures named, but their per-run numbers — cell counts, mesh quality
  tables — are not parsed yet.
- 13 of the 56 failure modes are `source=inferred`: never observed in the
  corpus. They may still be real — a regex that silently never matches looks
  like coverage and is not, so they are labelled rather than hidden.
- Benign chatter is filtered out of the catch-all warning counter.
  `Smoothing displacement` alone appeared 628 times across 520 utility logs;
  counting it would make every meshing run look alarming.

## What else is in this repository

| path | what |
|---|---|
| `tools/fetch_corpus.py` | rebuilds the 364-log validation corpus from public repositories |
| `tools/validate_corpus.py` | runs the parser over a directory of real logs and flags the shapes that mean it missed something |
| `skills/openfoam/` | an agent-facing guide to OpenFOAM itself: case anatomy, pre-flight validation, meshing, running headless, reading results without loading fields, and the failure-mode triage order |

The skill is not about this tool. It is about working with OpenFOAM at all
without loading a gigabyte into a context window, and `foamtriage` is one of
the commands it reaches for.

## Validate against your own logs

```bash
python3 tools/validate_corpus.py /path/to/your/logs
```

It asserts nothing about values it cannot know. It looks for the shapes that
mean the parser missed something: no solver name, a big log with no time loop,
a failure the table could not name, a field called diverging at a converged
residual. Exit 0 means nothing suspicious.

If it flags something, that log is a bug report worth opening.

## Licence

MIT.
