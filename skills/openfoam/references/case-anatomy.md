# Case anatomy and dictionary syntax

## Layout

```
case/
  0/            initial AND boundary conditions, one file per field
  0.orig/       pristine copy; Allrun copies it to 0/ before meshing
  constant/     physical properties, and polyMesh/ once meshed
  system/       how to solve: controlDict, fvSchemes, fvSolution, *Dict
  <time>/       written results, one directory per write
  processor*/   per-rank copies after decomposePar
  postProcessing/  functionObject output (CSV-ish, cheap to read)
  log.*         what the tools printed
```

`0.orig/` exists because meshing utilities overwrite `0/`. If a case has it,
never edit `0/` — edit `0.orig/` and re-run the Allrun sequence, or your change
is erased by the next `blockMesh`.

## system/

| file | holds | entries you will touch |
|---|---|---|
| `controlDict` | time control | `application`, `startFrom`, `startTime`, `endTime`, `deltaT`, `writeControl`, `writeInterval`, `adjustTimeStep`, `maxCo`, `maxDeltaT`, `functions{}` |
| `fvSchemes` | discretisation | `ddtSchemes`, `gradSchemes`, `divSchemes`, `laplacianSchemes` |
| `fvSolution` | linear solvers | `solvers{}` per field, `SIMPLE{}`/`PIMPLE{}`, `relaxationFactors{}` |
| `decomposeParDict` | parallel split | `numberOfSubdomains`, `method` (`scotch`, `hierarchical`, `simple`) |
| `blockMeshDict` | base mesh | `vertices`, `blocks`, `boundary` |
| `snappyHexMeshDict` | body-fitted mesh | `geometry`, `castellatedMeshControls`, `snapControls`, `addLayersControls` |

`numberOfSubdomains` must equal the rank count you launch with, or the run dies
immediately (`processor_dir_mismatch`).

## constant/

`transportProperties` (or `physicalProperties` in newer .org), `g`,
`turbulenceProperties` (renamed `momentumTransport` in .org v11+ — check which
exists rather than assuming), `thermophysicalProperties` for compressible and
reacting cases, `polyMesh/` after meshing.

## Fields in 0/

| field | meaning | appears in |
|---|---|---|
| `U` | velocity | everything |
| `p` | kinematic pressure | incompressible |
| `p_rgh` | pressure minus hydrostatic | buoyant, VoF, multiphase |
| `T` | temperature | heat transfer |
| `h`, `e` | enthalpy / internal energy | compressible (which one depends on the thermo `energy` entry) |
| `k`, `epsilon`, `omega`, `nut`, `nuTilda` | turbulence | RAS models |
| `alpha.<phase>` | phase fraction | VoF (`alpha.water`) |
| `<species>` | mass fractions | reacting (`CH4`, `O2`, …) |

Every field file needs a `boundaryField` entry for **every patch in the mesh**.
A patch with no entry is the single most common setup failure.

## Dictionary syntax

C-like, not C. Each entry ends in `;`; blocks are `{}`; lists are `()`.

```c
internalField   uniform (0 0 0);
boundaryField
{
    inlet   { type fixedValue; value uniform (1 0 0); }
    outlet  { type zeroGradient; }
    "wall.*" { type noSlip; }          // patch names accept regex, in quotes
}
```

Directives you will meet: `#include "file"`, `$variable` substitution,
`#calc "$a * 2"`, `#codeStream` (compiles C++ at read time — slow, and a
frequent cause of confusing first-run failures), `#remove`.

## Dimensions are positional

`[kg m s K kmol A cd]`

```c
dimensions [0 2 -2 0 0 0 0];   // m^2/s^2 — kinematic pressure
dimensions [0 1 -1 0 0 0 0];   // m/s     — velocity
dimensions [1 -1 -2 0 0 0 0];  // kg/(m s^2) = Pa — absolute pressure
dimensions [0 0 0 1 0 0 0];    // K       — temperature
```

Getting these wrong gives `incompatible dimensions for operation`, which names
the operation but not the file. Check the field you last edited.

## Boundary condition types worth knowing

`fixedValue`, `zeroGradient`, `noSlip`, `slip`, `symmetry`, `empty` (for 2D),
`cyclic`, `processor` (written by decomposePar, never by hand),
`inletOutlet` (free outflow, fixed inflow — the usual fix for
`continuity_not_removable`), `pressureInletOutletVelocity`, `totalPressure`,
`fixedFluxPressure`, `movingWallVelocity`, `calculated`,
and the wall functions `kqRWallFunction`, `epsilonWallFunction`,
`omegaWallFunction`, `nutkWallFunction`.

Using a type the build does not have gives `Unknown patchField type X`, and the
error message itself lists the valid names — read that list rather than guessing.
