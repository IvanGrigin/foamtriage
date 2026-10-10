# Running a case headless

## Use the case's own scripts when they exist

```bash
ls Allrun Allclean Allrun.pre 2>/dev/null
./Allrun            # does the whole sequence and writes log.<tool> per step
```

`Allrun` sources `$WM_PROJECT_DIR/bin/tools/RunFunctions`, which gives
`runApplication <tool>` and `runParallel <tool>`. Both redirect to `log.<tool>`
and **skip the step if that log already exists** — so a re-run after a failure
does nothing until you `./Allclean` or delete the log. This surprises people
constantly.

## Manual sequence

```bash
blockMesh                              # or surfaceFeatureExtract + snappyHexMesh
checkMesh                              # never skip
setFields                              # if the case has setFieldsDict
decomposePar                           # parallel only
mpirun -np 8 simpleFoam -parallel      # or: foamRun -solver incompressibleFluid
reconstructPar                         # parallel only, before post-processing
```

Rank count must equal `numberOfSubdomains` in `system/decomposeParDict`.

## Bound the run before starting it

An agent has no instinct for compute cost. A case that looks small can run for
hours. Before launching:

```bash
foamDictionary system/controlDict -entry endTime
foamDictionary system/controlDict -entry deltaT
foamDictionary system/controlDict -entry writeInterval
checkMesh 2>&1 | grep -i "^ *cells:"
```

To make a trial run cheap, cut `endTime` rather than killing it later:

```bash
foamDictionary system/controlDict -entry endTime -set 10
foamDictionary system/controlDict -entry writeControl -set timeStep
foamDictionary system/controlDict -entry writeInterval -set 5
```

State the expected cost before a long run. Do not start an unbounded one on your
own initiative.

## Restarting

```bash
foamDictionary system/controlDict -entry startFrom -set latestTime
foamListTimes            # confirm what is there to restart from
```

`startFrom latestTime` with `endTime` unchanged resumes; raising `endTime` first
continues further. For parallel cases the time directories must exist inside
`processor*/`, which they do if the run itself was parallel.

## Docker, when the host has no OpenFOAM

```bash
docker run --rm -it -v "$PWD":/case -w /case opencfd/openfoam-default:2412
docker run --rm -it -v "$PWD":/case -w /case openfoam/openfoam12-paraview510
```

Tutorials live in `$FOAM_TUTORIALS` inside the image, which is the cheapest
source of known-good cases and of real logs for testing tooling. On Apple
Silicon some images are amd64 only and run under emulation — fine for tutorials,
slow for real work.

## Watching a run without reading its log

```bash
foamtriage parse log.simpleFoam          # safe at any moment, including mid-run
```

A log being appended to parses fine; an unfinished run reports
`status: incomplete`. Poll this, never `tail -f` into context.

If you need convergence history as it happens, add the `residuals`
functionObject (see [reading-results.md](reading-results.md)) — it writes a small
CSV, which is cheaper to read than any log.
