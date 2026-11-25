"""Defect root-cause analysis (multi-reasoner) template.

Three-stage RelationalAI pipeline that turns a batch of final-test failures
into a defensible root-cause diagnosis over a serialized electronics-assembly
genealogy. The narrative: final-test failures have spiked from 1.9% in the
first build week to 6.6% in the second. Every finished unit carries its full material genealogy (which lots,
transitively, went into it through a multi-tier BOM) and its process history
(which machine and shift ran each operation). The chain works backward from
the failures to the smallest, most specific set of causes that explains them.

- Stage 1 -- Graph: backward reachability over the lot genealogy. A directed
  parent -> child graph on Lot is closed transitively so that each Unit is
  linked (`Unit.touches_lot`) to every lot consumed anywhere beneath it --
  the inverse of forward BOM dependency tracing. This is what surfaces a
  contaminated paste lot sitting two genealogy hops below the finished unit.
- Stage 2 -- Rules: contrast scoring. Each candidate Factor (a lot, machine,
  or shift) is scored by how concentrated defects are among the units it
  touches versus the plant-wide baseline (`Factor.lift`). A factor is flagged
  `is_suspect` only when its defect lift and support clear thresholds -- so a
  near-universal trunk lot or a high-volume machine (high coverage, ~1x lift)
  is screened out before optimization.
- Stage 3 -- Prescriptive: minimal-diagnosis set-cover MILP. Binary
  `Factor.is_root_cause` selects a smallest-cost set of suspect factors that
  together explain (cover) the defective units, with a per-unit slack so a
  few scattered baseline failures are left unexplained rather than forcing
  spurious causes. The objective penalizes collateral (good units a factor
  also touches), so the diagnosis prefers the specific deep root over the
  proximate sub-assembly lots that merely carry it.

Each stage enriches the shared ontology, and downstream stages consume those
enrichments as first-class properties -- the accretive enrichment pattern.

Modules: `failure_timeline.py` (failure rate per build week and the spike
onset), `genealogy.py` (Stage 1), `contrast_scoring.py` (Stage 2),
`diagnosis.py` (Stage 3), and `root_cause_evidence.py` (each suspect's defect
signature). Each module imports the modules whose declarations it reads.

Run:
    `rai models deploy --path model` deploys this package to the schemas in
    raiconfig.yaml and waits for its first refresh, which runs the solve; `python
    -m queries.root_cause_report` then prints the report from the deployed model.
"""

from . import root_cause_evidence
from .contrast_scoring import LIFT_THRESHOLD, MIN_DEFECTS, MIN_SUPPORT, PlantBaseline
from .diagnosis import (
    DiagnosisCost,
    DiagnosisResult,
    SolveStatus,
    num_cons,
    num_cover,
    num_min_objs,
    num_vars,
)
from .failure_timeline import BuildWeek, SpikeOnset
from .genealogy import num_edges, num_incidence, num_nodes
from .schema import Factor, Lot, Machine, Supplier, Unit, model
from .source import DATA_DIR

__all__ = [
    "DATA_DIR",
    "LIFT_THRESHOLD",
    "MIN_DEFECTS",
    "MIN_SUPPORT",
    "BuildWeek",
    "DiagnosisCost",
    "DiagnosisResult",
    "Factor",
    "Lot",
    "Machine",
    "PlantBaseline",
    "SolveStatus",
    "SpikeOnset",
    "Supplier",
    "Unit",
    "model",
    "num_cons",
    "num_cover",
    "num_edges",
    "num_incidence",
    "num_min_objs",
    "num_nodes",
    "num_vars",
    "root_cause_evidence",
]
