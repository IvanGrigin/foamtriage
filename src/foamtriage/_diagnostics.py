"""Known OpenFOAM failure modes.

The regexes and severities are domain data: every pattern here was observed in
a real log. The table was built by running the parser over a corpus of 364 logs
from 104 public repositories and adding every failure it could not name.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Final


class Severity(str, Enum):
    """Whether a named failure stopped the run."""

    FATAL = "fatal"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class DiagnosticSpec:
    """One recognisable failure mode."""

    id: str
    severity: Severity
    pattern: re.Pattern[str]
    groups: tuple[str, ...] = ()
    cause: str = ""
    fix_note: str = ""
    fix_extra: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.pattern.groups != len(self.groups):
            msg = (
                f"{self.id}: pattern has {self.pattern.groups} capturing groups "
                f"but {len(self.groups)} names"
            )
            raise ValueError(msg)


#: Failures that happen before OpenFOAM prints anything, so a missing header is
#: the truth about the log rather than a parser miss.
PRE_EXEC_REASONS: Final[frozenset[str]] = frozenset(
    {
        "mpi_not_enough_slots",
        "missing_case_directory",
        "mpi_executable_not_found",
        "mpi_run_as_root",
        "wrong_argument_count",
    }
)

DIAGNOSTICS: Final[Sequence[DiagnosticSpec]] = (
    DiagnosticSpec(
        id="missing_patch_field",
        severity=Severity.FATAL,
        pattern=re.compile("Cannot find patchField entry for (\\S+)"),
        groups=("patch",),
        cause="a patch present in the mesh has no matching entry in a field file's boundaryField block",
        fix_note="add a boundaryField entry for patch {patch} in the field file named by the error",
    ),
    DiagnosticSpec(
        id="undefined_keyword",
        severity=Severity.FATAL,
        pattern=re.compile('keyword (\\S+) is undefined in dictionary \\"([^\\"]+)\\"'),
        groups=("keyword", "dictionary"),
        cause="a required entry is missing from a dictionary the solver tried to read",
        fix_note="add keyword {keyword} to {dictionary}",
    ),
    DiagnosticSpec(
        id="incompatible_dimensions",
        severity=Severity.FATAL,
        pattern=re.compile("incompatible dimensions for operation"),
        groups=(),
        cause="quantities with different physical units were combined in one operation",
        fix_note="check that every coefficient includes its dimensions and the correct fields are used in expressions",
    ),
    DiagnosticSpec(
        id="unknown_patch_field_type",
        severity=Severity.FATAL,
        pattern=re.compile("Unknown patchField type (\\S+)"),
        groups=("type",),
        cause="the boundary condition type name in a field file is not recognised by this OpenFOAM build",
        fix_note="correct the type {type} to one of the valid names listed in the error message",
    ),
    DiagnosticSpec(
        id="cast_failure",
        severity=Severity.FATAL,
        pattern=re.compile("attempt to cast type (\\S+) to type (\\S+)"),
        groups=("from_type", "to_type"),
        cause="a boundary condition of the wrong kind was used where another kind was required",
        fix_note="replace the {from_type} boundary condition with one of kind {to_type} to match the field",
    ),
    DiagnosticSpec(
        id="field_mesh_mismatch",
        severity=Severity.FATAL,
        pattern=re.compile(
            "Number of cells in mesh and field do not match|size (\\d+) is not equal to the given value of (\\d+)"
        ),
        groups=("got", "expected"),
        cause="a field file was written for a different mesh than the one currently loaded",
        fix_note="regenerate the initial fields for the current mesh so size {got} matches the expected {expected}",
    ),
    DiagnosticSpec(
        id="missing_file",
        severity=Severity.FATAL,
        pattern=re.compile('[Cc]annot (?:find|open) file \\"?([^\\"\\n]+)'),
        groups=("path",),
        cause="a file the case needs, such as the mesh, a 0/ field, or a dictionary, is absent",
        fix_note="create or restore the missing file at {path} and check the case path settings",
    ),
    DiagnosticSpec(
        id="solution_singularity",
        severity=Severity.FATAL,
        pattern=re.compile("Solution singularity"),
        groups=(),
        cause="the linear system has no unique solution because pressure has no reference level in the closed domain",
        fix_note="set a pressure reference by adding pRefCell and pRefValue to the PIMPLE or SIMPLE dictionary",
        fix_extra={"pRefCell": 0, "pRefValue": 0},
    ),
    DiagnosticSpec(
        id="fp_exception",
        severity=Severity.FATAL,
        pattern=re.compile("Signal: Floating point exception|sigFpe::sigHandler"),
        groups=(),
        cause="a division by zero, square root of a negative number, or numeric overflow occurred during the run",
        fix_note="reduce the time step, tighten discretisation schemes, and check coefficients for zero or negative values",
    ),
    DiagnosticSpec(
        id="segfault",
        severity=Severity.FATAL,
        pattern=re.compile("Signal: Segmentation fault"),
        groups=(),
        cause="a memory fault occurred, commonly from a corrupt mesh or a parallel run count mismatched with the decomposition",
        fix_note="run checkMesh to validate the mesh and ensure the number of processes matches the decomposition",
    ),
    DiagnosticSpec(
        id="max_iterations",
        severity=Severity.WARNING,
        pattern=re.compile("Maximum number of iterations exceeded"),
        groups=(),
        cause="the linear solver reached its iteration cap without meeting its tolerance",
        fix_note="increase the iteration limit or relax tolerances, and check the mesh and initial conditions for the source",
    ),
    DiagnosticSpec(
        id="continuity_not_removable",
        severity=Severity.WARNING,
        pattern=re.compile(
            "Continuity error cannot be removed by adjusting the outflow"
        ),
        groups=(),
        cause="the boundary conditions fix the flux on every boundary so inflow and outflow cannot be balanced",
        fix_note="change at least one outlet to a boundary condition free to adjust, such as inletOutlet",
    ),
    DiagnosticSpec(
        id="negative_temperature",
        severity=Severity.FATAL,
        pattern=re.compile("Negative initial temperature|negative temperature"),
        groups=(),
        cause="the energy equation produced a temperature below absolute zero, which is unphysical",
        fix_note="reduce the time step, check the thermophysical settings, and verify boundary and initial temperatures",
    ),
    DiagnosticSpec(
        id="bounding",
        severity=Severity.WARNING,
        pattern=re.compile("^bounding (\\S+),"),
        groups=("field",),
        cause="field values were clipped back into their physical range because the solution went out of bounds",
        fix_note="watch repeated bounding of {field}; if frequent, review the turbulence and scalar scheme settings",
    ),
    DiagnosticSpec(
        id="processor_dir_mismatch",
        severity=Severity.FATAL,
        pattern=re.compile(
            "[Nn]umber of processor directories = (\\d+) (?:is not equal to|does not match) the number of processors = (\\d+)"
        ),
        groups=("found", "expected"),
        cause="the case was decomposed for {found} processors but is being run with {expected}",
        fix_note="re-run decomposePar with numberOfSubdomains set to {expected}, or launch with {found} ranks",
    ),
    DiagnosticSpec(
        id="zero_negative_cell_volume",
        severity=Severity.FATAL,
        pattern=re.compile("\\*\\*\\*\\s*Zero or negative cell volume"),
        groups=(),
        cause="checkMesh found cells with zero or inverted volume, so the mesh is unusable",
        fix_note="regenerate or repair the mesh so every cell has positive volume before retrying the run",
    ),
    DiagnosticSpec(
        id="zero_negative_face_area",
        severity=Severity.FATAL,
        pattern=re.compile("\\*\\*\\*\\s*Zero or negative face area"),
        groups=(),
        cause="checkMesh found faces collapsed to zero or negative area, from collapsed points or a bad snap",
        fix_note="check the snapping and mesh generation settings, then rebuild the mesh without degenerate faces",
    ),
    DiagnosticSpec(
        id="incorrectly_oriented_faces",
        severity=Severity.FATAL,
        pattern=re.compile(
            "\\*\\*\\*\\s*Error in face pyramids: (\\d+) faces are incorrectly oriented"
        ),
        groups=("faces",),
        cause="{faces} faces point away from their owner cell so fluxes would get the wrong sign",
        fix_note="fix the mesh so all {faces} incorrectly oriented faces point outward from their owner cell",
    ),
    DiagnosticSpec(
        id="severe_non_orthogonality",
        severity=Severity.WARNING,
        pattern=re.compile(
            "\\*\\*\\*\\s*Number of severely non-orthogonal[^:]*: (\\d+)"
        ),
        groups=("faces",),
        cause="{faces} faces meet their neighbours at a very oblique angle, degrading gradient accuracy",
        fix_note="raise nNonOrthogonalCorrectors in fvSolution or regenerate the mesh with better orthogonality",
    ),
    DiagnosticSpec(
        id="high_aspect_ratio",
        severity=Severity.WARNING,
        pattern=re.compile("\\*\\*\\*\\s*High aspect ratio cells found"),
        groups=(),
        cause="very stretched cells are present, which slows convergence and can destabilise the solution",
        fix_note="refine or re-mesh the stretched regions to reduce aspect ratios before trusting the results",
    ),
    DiagnosticSpec(
        id="mesh_checks_failed",
        severity=Severity.WARNING,
        pattern=re.compile("Failed (\\d+) mesh checks"),
        groups=("count",),
        cause="checkMesh reported {count} failing checks overall so mesh quality needs review",
        fix_note="review the {count} failing mesh checks in the checkMesh output and repair the mesh",
    ),
    DiagnosticSpec(
        id="unknown_function_type",
        severity=Severity.FATAL,
        pattern=re.compile("Unknown function type (\\S+)"),
        groups=("type",),
        cause="a functionObject of type {type} is not provided by this build, likely a typo or foreign fork",
        fix_note="correct the functionObject type {type} in controlDict to a valid name from the error message",
    ),
    DiagnosticSpec(
        id="mpi_abort",
        severity=Severity.FATAL,
        pattern=re.compile(
            "MPI_ABORT was invoked|mpirun detected that one or more processes exited with non-zero status"
        ),
        groups=(),
        cause="the parallel run was torn down because at least one rank died, so this is a symptom",
        fix_note="read the individual rank output above the abort to find the real error before changing anything",
    ),
    DiagnosticSpec(
        id="foam_warning",
        severity=Severity.WARNING,
        pattern=re.compile("-->\\s*FOAM Warning"),
        groups=(),
        cause="the run emitted warnings this table does not yet name specifically",
        fix_note="search the log for the FOAM Warning blocks and address each message shown there",
    ),
    DiagnosticSpec(
        id="missing_case_directory",
        severity=Severity.FATAL,
        pattern=re.compile('cannot open case directory \\"?([^\\"\\n]+)'),
        groups=("path",),
        cause="the solver was pointed at a case directory that does not exist",
        fix_note="run from the case directory, or correct the -case path; {path} was not found",
    ),
    DiagnosticSpec(
        id="mpi_not_enough_slots",
        severity=Severity.FATAL,
        pattern=re.compile("There are not enough slots available in the system"),
        groups=(),
        cause="MPI refused to start because the host offers fewer slots than ranks requested",
        fix_note="request no more ranks than available cores, or pass --oversubscribe to mpirun",
    ),
    DiagnosticSpec(
        id="solver_superseded",
        severity=Severity.WARNING,
        pattern=re.compile(
            "(\\S+) has been superseded and replaced by the more general"
        ),
        groups=("old_solver",),
        cause="the named executable is a shim and silently ran a different solver module",
        fix_note="{old_solver} is deprecated; call the replacement runner directly so the log says what ran",
    ),
    DiagnosticSpec(
        id="dict_syntax_error",
        severity=Severity.FATAL,
        pattern=re.compile("Wrong token type - expected (\\S+), found on line (\\d+)"),
        groups=("expected", "line"),
        cause="a dictionary has a syntax error and parsing stopped at an unexpected token",
        fix_note="fix the syntax at line {line}, where {expected} was expected; the log's next line names the file",
    ),
    DiagnosticSpec(
        id="entry_not_found",
        severity=Severity.FATAL,
        pattern=re.compile('Entry \'(\\S+)\' not found in dictionary \\"([^\\"]+)\\"'),
        groups=("entry", "dictionary"),
        cause="the dictionary {dictionary} lacks the required entry {entry}",
        fix_note="add entry {entry} to {dictionary}, or correct its spelling; the log names the file path",
    ),
    DiagnosticSpec(
        id="codestream_disabled",
        severity=Severity.FATAL,
        pattern=re.compile(
            "Loading shared libraries using case-supplied code may have been disabled"
        ),
        groups=(),
        cause="this build blocks compiling case-supplied code such as #codeStream for security reasons",
        fix_note="pre-compile the library into the installation, or allow case-supplied code in this environment",
    ),
    DiagnosticSpec(
        id="ami_failure",
        severity=Severity.FATAL,
        pattern=re.compile("Unable to set source and target faces"),
        groups=(),
        cause="an AMI interface could not pair its two patch sides, so no interpolation weights exist",
        fix_note="check that the two AMI patches overlap geometrically and verify the transform settings",
    ),
    DiagnosticSpec(
        id="failed_lookup",
        severity=Severity.FATAL,
        pattern=re.compile("failed lookup of (\\S+)"),
        groups=("object",),
        cause="the solver asked the object registry for {object} and it was never created",
        fix_note="ensure the file for {object} exists in constant/ with the correct name and a valid header",
    ),
    DiagnosticSpec(
        id="bad_file_header",
        severity=Severity.FATAL,
        pattern=re.compile("problem while reading header for object (\\S+)"),
        groups=("object",),
        cause="the file for {object} is missing its FoamFile header, truncated, or not a dictionary",
        fix_note="restore a valid FoamFile header in the file for {object}, or regenerate the file",
    ),
    DiagnosticSpec(
        id="gamg_no_coarse_levels",
        severity=Severity.FATAL,
        pattern=re.compile("No coarse levels created"),
        groups=(),
        cause="GAMG could not build a coarse grid hierarchy because the mesh is too small for it",
        fix_note="switch that field's solver to PCG or PBiCGStab, or lower nCellsInCoarsestLevel",
    ),
    DiagnosticSpec(
        id="mpi_executable_not_found",
        severity=Severity.FATAL,
        pattern=re.compile("mpirun was unable to find the specified executable"),
        groups=(),
        cause="MPI could not find the solver binary, so OpenFOAM never started",
        fix_note="source the OpenFOAM environment before running, and check the solver name for typos",
    ),
    DiagnosticSpec(
        id="mpi_run_as_root",
        severity=Severity.FATAL,
        pattern=re.compile("mpirun has detected an attempt to run as root"),
        groups=(),
        cause="Open MPI refuses to launch as root unless permitted, which is common inside containers",
        fix_note="run the case as an unprivileged user instead of root",
    ),
    DiagnosticSpec(
        id="wrong_argument_count",
        severity=Severity.FATAL,
        pattern=re.compile("Expected (\\d+) arguments but found (\\d+)"),
        groups=("expected", "found"),
        cause="the tool was called with {found} positional arguments instead of the {expected} it needs",
        fix_note="supply exactly {expected} arguments; the command provided {found}",
    ),
)

BY_ID: Final[Mapping[str, DiagnosticSpec]] = {d.id: d for d in DIAGNOSTICS}

#: ``bounding`` is consumed by the main pattern chain and synthesised afterwards
#: from the per-field counter, so it is excluded from the fall-through scan.
FALLTHROUGH: Final[Sequence[DiagnosticSpec]] = tuple(
    d for d in DIAGNOSTICS if d.id != "bounding"
)
