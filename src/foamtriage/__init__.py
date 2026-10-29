"""Turn an OpenFOAM log into a verdict that fits in a few hundred tokens.

>>> from foamtriage import FoamLog
>>> log = FoamLog.read("log.simpleFoam")
>>> log.status
<Status.FAILED: 'failed'>
>>> log.fix["note"]
'Courant number reached 41182 before the crash; limit the time step'
"""

from ._diagnostics import DIAGNOSTICS, DiagnosticSpec, Severity
from ._log import (
    SOLVED_TOL,
    Diagnostic,
    FoamLog,
    Kind,
    PhaseInfo,
    Residual,
    ResidualHistory,
    SolverSource,
    Status,
    Step,
    Trend,
)

__version__ = "0.2.0"

__all__ = [
    "DIAGNOSTICS",
    "SOLVED_TOL",
    "Diagnostic",
    "DiagnosticSpec",
    "FoamLog",
    "Kind",
    "PhaseInfo",
    "Residual",
    "ResidualHistory",
    "Severity",
    "SolverSource",
    "Status",
    "Step",
    "Trend",
    "__version__",
]
