# foamtriage reference

A single-file, standard-library-only parser that turns an OpenFOAM log of any
size into a verdict that fits in a few hundred tokens.

```bash
foamtriage capabilities                                  # read this once
foamtriage parse      log.X                              # the summary
foamtriage diagnose   log.X                              # named cause + fix
foamtriage residuals  log.X --field p --last 50          # drill-down
foamtriage steps      log.X --out steps.parquet          # per-step table to a file
```

## The contract

- Every command prints JSON on stdout and nothing else.
- `parse` output is **≤ 2 KB regardless of run length** — 10 000 steps and 6
  steps both fit. Lists are capped, with `*_total` giving the true count.
- No command ever returns file contents. Big output goes to a path you name.
- Errors are JSON too, with a `fix` field. You never parse a traceback.

## Exit codes

```
0  parsed; the run is healthy
1  parsed; the run failed, diverged, or finished with a runaway residual
2  bad arguments or unreadable file
```

Branch on these instead of reading the JSON when all you need is whether to go on.

## Scale, measured

| | |
|---|---|
| 10 000-step log | 10 648 456 B (~2.66 M tokens) |
| its `parse` summary | 1 200 B (~300 tokens) |
| ratio | ~8 900× |
| parse time | 0.32 s |
| per-step CSV / Parquet | 360 KB / 162 KB |

## Summary fields

| field | meaning |
|---|---|
| `kind` | `solver`, `utility`, `launcher_failure`, `unknown` |
| `status` | `converged`, `completed`, `diverged`, `failed`, `incomplete` |
| `reason` | machine-readable; a diagnostic id when the table named the failure |
| `fix` | the one action to take, already specialised to this log |
| `diverging` | field names whose residuals ran away — **survives the residuals cap** |
| `diagnostics` | named modes, fatal first; `cause`/`fix_note` via `diagnose` |
| `residuals` | capped at the most alarming; `residuals_total` is the real count |
| `fields` | residual field names; `region/field` on multi-region runs |
| `solver`, `exec`, `solver_modules` | run name, command line, modules a `foamRun` loaded |
| `solver_source` | `exec`, `module`, `filename` or empty — provenance of the name. `filename` means the header was stripped and the name was inferred |
| `fork`, `version`, `build` | `org`, `com`, `extend`, `rapidcfd` or `unknown`, and whatever the log said |
| `steady`, `n_steps`, `last_time`, `wallclock_s` | time loop |
| `courant_max`, `interface_courant_max` | stability |
| `phases` | VoF phase fractions: drift and min/max bounds — mass conservation |
| `temperature_range` | per region, or `global` for single-region solvers |
| `rho_range` | compressible density bounds, as `[min, max]` |
| `mesh_update_s` | total time in `mesh.update()` on dynamic-mesh runs |
| `bounding` | per-field count of clipping warnings |
| `continuity_cumulative_last` | last cumulative continuity error |

## Reading it in the right order

```bash
foamtriage parse log.X > /dev/null; rc=$?
# rc=0 → done, the run is fine
# rc=1 → foamtriage diagnose log.X, act on .fix
# rc=2 → fix the path
```

Then, only if you need the shape of the history:

```bash
foamtriage residuals log.X --field p --last 50     # ~4 KB, 50 rows
```

## Python API

```python
from foamtriage import FoamLog, Status

log = FoamLog.load("log.simpleFoam")
log.status is Status.FAILED  # the verdict as an enum
log.healthy  # False when it failed, diverged or finished dirty
log.summary()  # the capped payload, <= 2 kB
log.residual_history("p", last=50)
log.steps  # per-step rows, never in the summary
```

`foamtriage.DIAGNOSTICS` is the failure table, `foamtriage.SOLVED_TOL` the
absolute residual tolerance behind trend verdicts, and `foamtriage capabilities`
prints the machine-readable self description.

## Validating it against your own logs

```bash
python3 tools/validate_corpus.py /path/to/your/logs
```

Validated against a corpus of 364 real logs (23.9 MB) from public
repositories: 0 suspicions, 0 crashes, parsed in 0.9 s.

Asserts nothing about values it cannot know. It looks for the shapes that mean
the parser missed something: no solver name, a big log with no time steps, a
failure the table could not name, a field called diverging at a converged
residual. Exit 0 means nothing suspicious.

This is the check that matters. Synthetic fixtures prove the structure; only
real logs prove the wording, and every wording bug found so far came from real
logs — the `Time = 1s` unit suffix, the capitalised `Cannot find file`, the
absent `-solver` argument, the per-region `Selecting solver` lines.

## Limits

- Trend verdicts use a 1e-6 absolute tolerance plus ratio tests. Tuned against
  real logs, not derived from solver tolerances.
- The table names 37 modes. Anything else is `reason: fatal_error` — read the
  log tail.
- Utility logs are recognised by `Exec` name but their contents are not parsed.
- `snappyHexMesh` strings are a deliberate gap, not an oversight.
