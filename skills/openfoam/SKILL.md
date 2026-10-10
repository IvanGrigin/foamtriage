---
name: openfoam
description: Run, diagnose and read OpenFOAM CFD cases without drowning in output. Use when working with an OpenFOAM case directory (0/, constant/, system/), a solver log, a blockMeshDict or controlDict, or when asked to run, debug, restart, mesh or post-process a CFD simulation. Covers both forks (openfoam.org and openfoam.com), the foamRun/foamMultiRun module runners, multi-region and multiphase cases.
---

# OpenFOAM for agents

## The one rule

OpenFOAM's output is sized for disks, not context windows.

| artifact | real size | as tokens |
|---|---|---|
| 10 000-step solver log | ~10 MB | ~2.6 M |
| one field, 1M-cell mesh, one time | ~20 MB | ~5 M |
| a case's time directories | GB | — |

**Never read a log or a field file into context.** Every number you need has a
command that returns only that number. Reading `log.simpleFoam` to find out
whether it converged costs about ten thousand times more than asking.

| you want | do NOT | DO | cost |
|---|---|---|---|
| did it converge, and why not | read the log | `foamtriage parse log.X` | ~300 tok |
| the named cause of a crash | grep the log | `foamtriage diagnose log.X` | ~400 tok |
| a convergence history | read the log | `foamtriage residuals log.X --field p --last 50` | ~4 KB |
| one dictionary value | read the file | `foamDictionary system/controlDict -entry endTime` | ~20 tok |
| which times were written | `ls` the case | `foamListTimes` | small |
| a force, flux or field range | read fields | `postProcess -func '...'` or a `functions` entry | small |

## Orient first

```bash
foamtriage capabilities                 # what the log tool can do, once
cat system/controlDict | head -30    # application/solver, time controls
foamDictionary system/controlDict -entry application    # or just this
ls 0 constant system                 # fields, properties, dictionaries
foamListTimes                        # what has already been written
```

Two forks exist and differ in places that break naive parsing. Check which you
have before trusting any version-specific advice: see
[references/forks-and-versions.md](references/forks-and-versions.md).

## Work in this order

Each step is cheap and catches what the next step would pay for dearly.

1. **Validate the case before running.** A missing boundary condition costs one
   second to find and forty minutes to discover after meshing.
   See [references/validating.md](references/validating.md).
2. **Mesh, then check the mesh.** `checkMesh` failures make every later result
   meaningless. See [references/meshing.md](references/meshing.md).
3. **Run headless, bounded.** Never launch an unbounded run on a whim; estimate
   first. See [references/running.md](references/running.md).
4. **Diagnose from the summary, not the log.**
   See [references/failure-modes.md](references/failure-modes.md).
5. **Extract results as scalars.**
   See [references/reading-results.md](references/reading-results.md).

## Editing a case

Do not rewrite dictionary files. OpenFOAM ships a tool that edits them in place
with correct syntax, and it is the only safe way for an agent to change a case:

```bash
foamDictionary system/controlDict -entry endTime -set 500
foamDictionary system/fvSolution -entry solvers/p/tolerance -set 1e-8
foamDictionary 0/U -entry boundaryField/outlet -set '{type zeroGradient;}'
foamDictionary system/controlDict -entry functions -remove
```

Hand-written dictionary syntax is a common source of silent failure: it is
C-like but not C, supports `#include`, `$variable`, `#calc` and `#codeStream`,
and dimension vectors are positional. See
[references/case-anatomy.md](references/case-anatomy.md) before writing one by hand.

## The log tool

`foamtriage` turns any log into a verdict that fits in a few hundred tokens.
Full reference: [references/foamtriage.md](references/foamtriage.md).

```bash
foamtriage parse log.simpleFoam      # summary, <= 2 KB whatever the run length
echo $?                           # 0 healthy, 1 run problem, 2 unreadable
```

Branch on the exit code rather than reading the JSON when you only need to know
whether to continue.

A caution that applies to every tool here: `status` can be `completed` while the
answer is worthless. Always check `reason` and `diverging` too — a run that
reached `End` with a runaway residual reports
`completed / end_reached_with_divergence`.

## Honest limits of this skill

- The diagnostics table names 37 failure modes, built by running the parser over
  364 real logs (23.9 MB) from public repositories and adding every failure it
  could not name. Anything else surfaces as `reason: fatal_error` with the raw
  log untouched — then you read the log's tail, not the whole file.
- Utility logs (`blockMesh`, `checkMesh`, `snappyHexMesh`) are recognised but
  their contents are not parsed; read their last ~40 lines directly.
- `snappyHexMesh` failure strings are deliberately absent from the table rather
  than guessed. A regex that silently never matches is worse than a known gap.
- Version-specific claims are marked where they are unverified.
