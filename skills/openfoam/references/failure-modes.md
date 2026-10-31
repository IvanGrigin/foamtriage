# Failure modes and triage

## Triage order

Work down this list. Each step is cheaper than the one below it, and the first
hit is usually the answer.

1. **`foamtriage parse log.X`** — exit code 1 means something is wrong; `reason`
   names it when the table knows it.
2. **`foamtriage diagnose log.X`** — the named cause, in prose, plus the one action
   to take. Stop here for the 27 modes below.
3. **`reason: fatal_error` or `fatal_io_error`** — the run died with a message
   the table does not name. Read the log's **tail**, not the log:
   `tail -40 log.X`. OpenFOAM puts the fatal block at the end, with a file and
   line number.
4. **`status: completed` but `diverging` non-empty** — the run finished and the
   answer is worthless. Go to the physics, not the setup: time step, relaxation,
   mesh quality, boundary conditions.
5. **Nothing named, nothing diverging, results still wrong** — that is a modelling
   question, not a log question. Check `checkMesh`, then the schemes in
   `fvSchemes`, then the physics.

## The cardinal confusion

`status` answers "did the executable finish", not "is the answer any good".

| status | reason | means |
|---|---|---|
| `converged` | `criteria_reached` | steady run met its residual criteria — the good case |
| `completed` | `end_reached` | reached `endTime` cleanly |
| `completed` | `end_reached_with_divergence` | **finished, but a residual ran away; the result is junk** |
| `diverged` | `residual_divergence` | residuals blew up, no clean exit |
| `failed` | a diagnostic id | died; the id names why |
| `incomplete` | `truncated_log` | still running, or killed, or the log is a fragment |

## Divergence verdicts, and their limits

A field is called diverging on a final-residual series using a 1e-6 absolute
tolerance first and ratio tests second. The absolute floor matters: real logs
routinely start a field at exactly 0, and a pure ratio test then calls a
converged 1e-9 "diverging". That exact false positive hit two of three real
interFoam logs before the floor was added.

Fields that are never really solved (`rho` under the `diagonal` solver: zero
residual, zero iterations) are reported as `not_solved`, not `stalled`, so they
do not crowd real fields out of the capped summary.

## The 37 named modes

`fatal` means the run stopped. `warning` means it continued and you should care.
29 fatal, 8 warning. The table was built by running the parser over 364 real
logs from public repositories and adding every failure it could not name — the
most common single one, `entry_not_found`, accounted for 20 of them.

| id | severity | cause |
|---|---|---|
| `missing_patch_field` | fatal | a patch present in the mesh has no matching entry in a field file's boundaryField block |
| `undefined_keyword` | fatal | a required entry is missing from a dictionary the solver tried to read |
| `incompatible_dimensions` | fatal | quantities with different physical units were combined in one operation |
| `unknown_patch_field_type` | fatal | the boundary condition type name in a field file is not recognised by this OpenFOAM build |
| `cast_failure` | fatal | a boundary condition of the wrong kind was used where another kind was required |
| `field_mesh_mismatch` | fatal | a field file was written for a different mesh than the one currently loaded |
| `missing_file` | fatal | a file the case needs, such as the mesh, a 0/ field, or a dictionary, is absent |
| `fp_exception` | fatal | a division by zero, square root of a negative number, or numeric overflow occurred during the run |
| `segfault` | fatal | a memory fault occurred, commonly from a corrupt mesh or a parallel run count mismatched with the decomposition |
| `max_iterations` | warning | the linear solver reached its iteration cap without meeting its tolerance |
| `continuity_not_removable` | fatal | the boundary conditions fix the flux on every boundary so inflow and outflow cannot be balanced |
| `negative_temperature` | fatal | the energy equation produced a temperature below absolute zero, which is unphysical |
| `bounding` | warning | field values were clipped back into their physical range because the solution went out of bounds |
| `processor_dir_mismatch` | fatal | the case was decomposed for {found} processors but is being run with {expected} |
| `zero_negative_cell_volume` | fatal | checkMesh found cells with zero or inverted volume, so the mesh is unusable |
| `zero_negative_face_area` | fatal | checkMesh found faces collapsed to zero or negative area, from collapsed points or a bad snap |
| `incorrectly_oriented_faces` | fatal | {faces} faces point away from their owner cell so fluxes would get the wrong sign |
| `severe_non_orthogonality` | warning | {faces} faces meet their neighbours at a very oblique angle, degrading gradient accuracy |
| `high_aspect_ratio` | warning | very stretched cells are present, which slows convergence and can destabilise the solution |
| `mesh_checks_failed` | warning | checkMesh reported {count} failing checks overall so mesh quality needs review |
| `unknown_function_type` | fatal | a functionObject of type {type} is not provided by this build, likely a typo or foreign fork |
| `mpi_abort` | fatal | the parallel run was torn down because at least one rank died, so this is a symptom |
| `foam_warning` | warning | the run emitted warnings this table does not yet name specifically |
| `missing_case_directory` | fatal | the solver was pointed at a case directory that does not exist |
| `mpi_not_enough_slots` | fatal | MPI refused to start because the host offers fewer slots than ranks requested |
| `solver_superseded` | warning | the named executable is a shim and silently ran a different solver module |
| `dict_syntax_error` | fatal | a dictionary has a syntax error and parsing stopped at an unexpected token |
| `entry_not_found` | fatal | the dictionary {dictionary} lacks the required entry {entry} |
| `codestream_disabled` | fatal | this build blocks compiling case-supplied code such as #codeStream for security reasons |
| `ami_failure` | fatal | an AMI interface could not pair its two patch sides, so no interpolation weights exist |
| `failed_lookup` | fatal | the solver asked the object registry for {object} and it was never created |
| `bad_file_header` | fatal | the file for {object} is missing its FoamFile header, truncated, or not a dictionary |
| `gamg_no_coarse_levels` | fatal | GAMG could not build a coarse grid hierarchy because the mesh is too small for it |
| `mpi_executable_not_found` | fatal | MPI could not find the solver binary, so OpenFOAM never started |
| `mpi_run_as_root` | fatal | Open MPI refuses to launch as root unless permitted, which is common inside containers |
| `wrong_argument_count` | fatal | the tool was called with {found} positional arguments instead of the {expected} it needs |

Each carries a `fix_note` already specialised to the log — the offending patch
name, the missing keyword, the actual Courant number. Read it from
`foamtriage diagnose`.

## Specific diagnosis beats generic

When a run dies by floating-point exception after the Courant number climbed
past 1, the generic advice ("check coefficients for zero or negative values") is
true and useless. The table overrides it:

```json
{"adjustTimeStep": true, "maxCo": 0.9,
 "note": "Courant number reached 41182 before the crash; limit the time step"}
```

Symptoms are also ranked below causes. A parallel run that dies shows both
`fp_exception` and `mpi_abort`; the fatals sort by line, so the real cause comes
first and `reason` is `fp_exception`, not the MPI teardown that followed.

## Known gap

`snappyHexMesh` failure strings are absent on purpose. A regex that silently
never matches looks like coverage and is not. When snappy fails, read its log
tail — see [meshing.md](meshing.md) for the usual causes.
