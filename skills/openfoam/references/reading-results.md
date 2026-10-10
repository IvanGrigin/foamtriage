# Getting numbers out without reading fields

One field on a million-cell mesh is tens of megabytes of per-cell values. There
is no situation in which reading one into context is the right move. Everything
below returns scalars or small tables.

## Ask the solver to measure, while it runs

The `functions` block in `system/controlDict` makes OpenFOAM write small CSV
files to `postProcessing/` during the run. This is the cheapest possible path:
the numbers exist before you ask for them.

```c
functions
{
    residuals
    {
        type            residuals;
        libs            ("libutilityFunctionObjects.so");
        writeControl    timeStep;
        fields          (U p k epsilon);
    }
    forces
    {
        type            forceCoeffs;
        libs            ("libforces.so");
        patches         (wing);
        // plus the usual rhoInf/magUInf/lRef/Aref entries
    }
    inletFlux  { type surfaceFieldValue; regionType patch; name inlet;
                 operation sum; fields (phi); }
    Trange     { type fieldMinMax; fields (T); }
}
```

The `residuals` functionObject deserves special mention: it gives you
convergence history as a tidy CSV, which is both cheaper and more reliable than
parsing it back out of a log.

Add one to an existing case without hand-editing:

```bash
foamDictionary system/controlDict -entry functions/Trange \
  -set '{type fieldMinMax; libs ("libfieldFunctionObjects.so"); fields (T);}'
```

## Ask after the fact

```bash
foamListTimes                                   # what is available
postProcess -func 'fieldMinMax(U,p)' -latestTime
postProcess -func 'patchIntegrate(patch=outlet,field=phi)' -latestTime
postProcess -func 'probes' -latestTime          # needs a probes dict
```

`-latestTime` matters: without it `postProcess` walks every written time and can
take as long as the run did.

## Then read the small files

```bash
ls postProcessing/                              # one directory per function
foamtriage residuals log.simpleFoam --field p --last 50   # or straight from the log
```

`postProcessing/*/*/*.dat` files are a few KB and safe to read. Time directories
(`0.1/`, `0.2/`, …) are not.

## What to read, by question

| question | command |
|---|---|
| did it converge | `foamtriage parse log.X` |
| which field misbehaved | `foamtriage parse log.X` → `diverging`, `residuals` |
| convergence shape | `foamtriage residuals log.X --field p --last 50` |
| drag/lift | `forceCoeffs` functionObject → `postProcessing/forces/` |
| mass balance | `surfaceFieldValue` on inlet and outlet patches |
| hot spot | `fieldMinMax` on `T`, or `foamtriage parse` → `temperature_range` |
| mass conservation in VoF | `foamtriage parse` → `phases` (fraction drift, min/max bounds) |
| time spent on mesh motion | `foamtriage parse` → `mesh_update_s` |
| per-step wall clock | `foamtriage steps log.X --out steps.parquet` then aggregate |

## Visual output

`foamToVTK` or `paraFoam` produce files for a human to look at. Generate them on
request; never try to interpret the geometry yourself from field values.
