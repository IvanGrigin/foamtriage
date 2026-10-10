# Validate before you run

A solver that dies after forty minutes of meshing and compute teaches you
nothing a one-second check could not. Run these in order.

## 1. Every patch has a boundary condition in every field

This is the most common failure in OpenFOAM, full stop.

```bash
# patches the mesh actually has
foamDictionary constant/polyMesh/boundary -keywords
# what each field declares
for f in 0/*; do
  echo "== $f"; foamDictionary "$f" -entry boundaryField -keywords
done
```

Compare the two lists. A patch present in the first and absent in the second
gives `Cannot find patchField entry for <patch>` the moment the solver starts.

Before the mesh exists, read the patch names from `system/blockMeshDict`
(`boundary` block) instead.

## 2. The decomposition matches the launch

```bash
foamDictionary system/decomposeParDict -entry numberOfSubdomains
ls -d processor* 2>/dev/null | wc -l
```

These and your `mpirun -np N` must agree. Mismatch gives
`processor_dir_mismatch`, or a cryptic MPI teardown.

## 3. The solver and the dictionaries agree

`fvSolution` needs a `solvers` entry for every field the solver will solve, and
a `SIMPLE` or `PIMPLE` block matching the solver family (steady solvers read
`SIMPLE`, transient read `PIMPLE`). A missing entry gives
`keyword X is undefined in dictionary "Y"` — which names both, so it is cheap to
fix once it happens, but cheaper to avoid.

For a closed domain with no fixed-pressure boundary, `fvSolution` must set a
pressure reference, or you get `Solution singularity`:

```bash
foamDictionary system/fvSolution -entry SIMPLE/pRefCell -set 0
foamDictionary system/fvSolution -entry SIMPLE/pRefValue -set 0
```

## 4. Dimensions

Check the fields you edited. `dimensions` is positional (see
[case-anatomy.md](case-anatomy.md)); a wrong vector is accepted at read time and
fails later as `incompatible dimensions for operation`.

## 5. The case opens at all

```bash
foamDictionary system/controlDict -entry application   # parses the dict too
foamListTimes                                          # requires a readable case
```

Both fail fast if the case directory is wrong or a dictionary is malformed,
giving `missing_case_directory` or a parse error with a file and line number.

## 6. Estimate the cost before launching

```bash
checkMesh 2>&1 | tail -40 | grep -i cells      # how big
foamDictionary system/controlDict -entry endTime
foamDictionary system/controlDict -entry deltaT
```

Steps ≈ `(endTime - startTime) / deltaT`, unless `adjustTimeStep yes`, in which
case the step count is governed by `maxCo` and cannot be known in advance. Cells
times steps is the rough cost. If that product is large, say so before starting
rather than after.
