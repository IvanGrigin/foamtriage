# Meshing, and reading checkMesh cheaply

## Order

```bash
blockMesh                     # always first: makes the background mesh
surfaceFeatureExtract         # if snappy will use feature edges
snappyHexMesh -overwrite      # body-fitted mesh from STL geometry
checkMesh -allGeometry -allTopology
```

`snappyHexMesh` without `-overwrite` writes successive time directories instead
of replacing `constant/polyMesh`, which then confuses the solver about what the
mesh is.

## checkMesh is not optional

A mesh that fails checks produces numbers that look plausible and are wrong.
Its output is long; read only the verdict:

```bash
checkMesh 2>&1 | tail -40
```

Failures are prefixed `***`, the summary line is `Failed N mesh checks.` or
`Mesh OK.`

| line | meaning | what to do |
|---|---|---|
| `***Zero or negative cell volume` | inverted or collapsed cells | regenerate; not fixable in place |
| `***Zero or negative face area` | degenerate faces | usually a bad snap; revisit snappy settings |
| `***Error in face pyramids: N faces are incorrectly oriented` | fluxes would get the wrong sign | mesh must be fixed |
| `***Number of severely non-orthogonal faces: N` | oblique cells; gradients degrade | raise `nNonOrthogonalCorrectors`, or re-mesh |
| `***High aspect ratio cells found` | very stretched cells | slows convergence; re-mesh the region |
| `Mesh OK.` | no failures | proceed |

Non-orthogonality and aspect ratio are warnings: the run will proceed and may
still be usable. Zero volumes and bad orientation are not.

`foamtriage` recognises a `checkMesh` log as `kind: utility` and names the failures
above, but does not parse the rest of its output — for anything else, read the
last forty lines.

## snappyHexMesh

Its failures are the least predictable part of the toolchain and its exact
messages are **not** in the diagnostics table — they were left out rather than
guessed, because a regex that silently never matches is worse than a known gap.
When snappy misbehaves, read the tail of its log directly.

Common causes worth checking first: `locationInMesh` sitting inside solid
geometry or exactly on a face, an STL that is not closed, units mismatched
between STL (often mm) and the case (m), and refinement levels that explode the
cell count.

```bash
foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/locationInMesh
```

## Parallel meshing

`snappyHexMesh` parallelises; `blockMesh` does not. For a parallel snappy run
decompose first, and remember that `reconstructParMesh` (not `reconstructPar`)
puts the mesh back together.
