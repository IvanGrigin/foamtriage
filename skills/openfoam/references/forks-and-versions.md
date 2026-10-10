# Two forks, and what actually differs

Both call themselves OpenFOAM. Tell them apart before applying version-specific
advice.

Across 364 real logs the split was 175 .org, 180 .com, 2 RapidCFD, 1
foam-extend, 6 with no banner at all.

| | openfoam.org (Foundation) | openfoam.com (ESI / OpenCFD) |
|---|---|---|
| version string | `12`, `11`, `7` | `v2412`, `2506`, `2206` |
| banner `Website:` | `https://openfoam.org` | `www.openfoam.com` |
| `Build :` line | `12-a4f91c3b7e02` | `_8993a5b1-20241231 OPENFOAM=2412 version=v2412` |
| solver invocation | v11+ via `foamRun -solver <module>` | classic per-solver executables |
| release cadence | yearly-ish, integer versions | twice a year, `vYYMM` |

`foamtriage parse` reports `fork` as `org`, `com` or `unknown`, and `version` as
whatever the log actually said — both `v2412` and `2506` styles occur.

## Five forks, not two

| fork | banner marker |
|---|---|
| `org` | `Website: https://openfoam.org`, or `Web: www.OpenFOAM.org` on older builds |
| `com` | `Website: www.openfoam.com`, `OPENFOAM=2412` in `Build`, or `Using: OpenFOAM-2412 (2412) - visit www.openfoam.com` |
| `extend` | `OpenFOAM Extend Project`, `www.extend-project.de` |
| `rapidcfd` | `RapidCFD by simFlow (sim-flow.com)` — a GPU port, no `Version:` line at all |
| `unknown` | no banner: stdout captured without a header, or the run died before OpenFOAM started |

Three traps in that table, all found by parsing real logs:

- the field is **`Web:`** on builds up to roughly v5, `Website:` after;
- the domain is written `www.OpenFOAM.org` with capitals as often as lowercase;
- some wrappers print no banner box at all, only `Using: OpenFOAM-2412 ...`.

Do not look for the banner in the first N lines. A 64-rank parallel run prints
its startup preamble once per rank, and some builds emit hundreds of debug
lines, so the domain line can be a thousand lines down.

## Differences that break naive parsing

These were found by running a parser against real logs, not from documentation.

**The time line carries a unit in .org v11+.**

```
Time = 1s                 .org v11+
Time = 1.19904e-05s       .org v13
Time = 0.000119976        .com, and older .org
```

A regex anchored right after the number silently matches nothing on the newer
form, which looks like "the run did one step".

**`foamRun` does not name the solver.** In .org v11+ physics lives in modules:

```
Exec : foamRun -solver incompressibleFluid    module on the command line
Exec : foamRun                                module from system/controlDict,
                                              visible only as
                                              "Selecting solver incompressibleFluid"
```

The argument is absent more often than present. One `foamRun` can also load
several modules (a `functions` run instantiates the physics too), so a log may
contain more than one `Selecting solver` line.

**`foamMultiRun` loads one module per region.** Its `Selecting solver` lines name
regions' modules (`solid`, `fluid`), not the run. Taking the last one names the
run after whichever region came last.

**Old solver names are shims.** In .org v11+, and the wording varies:

```
chtMultiRegionFoam has been superseded and replaced by the more general
foamMultiRun solver module executor which will be executed instead:

rhoSimpleFoam has been superseded and replaced by the more general
fluid solver module which will be executed using

    foamRun -solver fluid
```

So `Exec` says one thing and the actual solver is another. `foamtriage` reports this
as the `solver_superseded` diagnostic.

**Renamed dictionaries.** `turbulenceProperties` became `momentumTransport` in
.org v11+; `transportProperties` became `physicalProperties` in places. Check
which file exists rather than assuming:

```bash
ls constant/
```

## Residual printing can be switched off entirely

One real `reactingFoam` log ran 683 steps and printed no `Solving for` lines at
all — only `min/max(T)` and continuity errors. `fields: []` on a long run is
therefore a legitimate state, not a parse failure. Use the `residuals`
functionObject if you need the history (see
[reading-results.md](reading-results.md)).

That log also showed a second temperature format: `min/max(T) = 300, 1200.0305`
alongside the `Min/max T:300 348.2` that multi-region solvers print.

## Unverified

Version 13 exists on .org and parses with the v11+ rules, but its specific
differences have not been checked. ESI-side `interFoam` prints `alpha.water`
with residuals in recent versions and without them in older ones; both forms
parse, but the bare form has not been seen in a real log.
