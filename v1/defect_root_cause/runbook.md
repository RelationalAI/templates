# Runbook: Defect Root-Cause Analysis — Multi-Reasoner Walkthrough

Final-test failures on a consumer-electronics assembly line have jumped — from a ~1.9% baseline in week 1 to 6.6% in week 2 and 8.3% by week 3, once an incident lands at the start of week 2. Every serialized unit carries its full material genealogy (which lots it consumed, transitively, through a four-tier bill of materials) and its process history (which machine and shift ran each operation). The chain locates the onset, then works backward from the failures to the smallest, most specific set of root causes — resisting the pull of high-volume factors that merely touch everything.

## The chain

```
Ontology: 6 source-data concepts (SKU, BillOfMaterials, Supplier, Machine, Lot,
Unit) plus unit-lot consumption, unit process history, and a Factor candidate
set. 2,500 units (142 defective, 5.68%), 105 lots, 162 genealogy edges,
118 candidate factors. The chain locates the onset, then works backward to a
minimal root-cause diagnosis.

  ─────────────────────────────────────────────────────────────────
  EXAMINE   Descriptive   ──►  final-test failure rate by build week
   /rai-querying               1.9% (wk1) -> 6.6% (wk2) -> 8.3% (wk3);
                               spike onset = week 2.
  ─────────────────────────────────────────────────────────────────
  STAGE 1   Graph         ──►  Unit.touches_lot  (57,133 incidence facts)
   /rai-graph-analysis         Transitive backward reachability over the
                               105-lot / 162-edge parent->child genealogy.
  ─────────────────────────────────────────────────────────────────
  STAGE 2   Rules         ──►  Factor.lift, Factor.is_suspect  (10 suspects)
   /rai-rules-authoring        Defect lift vs. the 5.68% baseline; screens
                               out high-coverage / low-lift trunk factors.
  ─────────────────────────────────────────────────────────────────
  STAGE 3   Prescriptive  ──►  Factor.is_root_cause (2), DiagnosisResult
   /rai-prescriptive-          OPTIMAL · obj 46.32 · {SP-0423, REF-02}
   problem-formulation         explain 120/142 defects (85% coverage).
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a manufacturing genealogy ontology from the CSVs in data/. Model finished Units with their final-test result and build week, the multi-tier SKU bill of materials, material Lots with a parent->child genealogy (a built lot consumes its input lots) and receipt dates, each unit's directly-consumed lots and its process history (machine and shift per operation), and a Factor concept enumerating the candidate root causes — every lot, machine, and shift.
```

**Response**

Concepts bound to the bundled CSVs: `SKU` (20, four tiers), `BillOfMaterials` (26 edges), `Supplier` (8), `Machine` (10, with `calibration_age_days`), `Lot` (105, with `received_date` and a self-referencing `consumes` genealogy relationship), `Unit` (2,500, with `defective` / `defect_type` / `shift` / `build_week` and `consumes_lot` + `ran_on` relationships), and `Factor` (118 candidates with per-kind back-pointers to a lot, machine, or shift). Genealogy edges total 162.

### 2. Examine ontology

**Prompt**

```
/rai-querying How many units are there, how many are defective, what failure rate is that, and what is the defect-type mix?
```

**Response**

2,500 `Unit` rows, 142 defective — a 5.68% final-test failure rate. Defect-type mix: `SOLDER_BRIDGE` 65, `COLD_SOLDER` 57, `MISSING_COMPONENT` 9, `TOMBSTONE` 7, `MISALIGNMENT` 4. The two dominant signatures (solder bridge, cold solder) hint at a thermal/reflow issue and a paste/placement issue respectively.

### 3. Locate the spike onset

**Prompt**

```
/rai-querying Before touching genealogy: when did the failures start climbing? Roll the final-test failure rate up by build week, and identify the onset — the first week whose rate runs well above the opening week's baseline.
```

**Response**

Failure rate by build week: 1.9% (week 1, 795 units) → 6.6% (week 2, 852) → 8.3% (week 3, 853). The onset is week 2 — the rate more than triples off the week-1 baseline. This narrows the search before it starts: the rest of the chain interrogates what entered the line at the week-2 boundary (lots received then, equipment that drifted then), not the whole three-week history.

### 4. Discover reasoner questions

**Prompt**

```
/rai-discovery Failures climb sharply at a week-2 onset. Every unit carries its full material genealogy and process history. Which RAI reasoners do we need, in what order, to work backward from the failures to the smallest defensible set of root causes — rather than just a long list of things the bad units have in common?
```

**Response**

Plans the backward chain on the shared ontology: graph (`/rai-graph-analysis`) to close the lot genealogy transitively and attribute every upstream lot to the units that carry it; rules (`/rai-rules-authoring`) to contrast-score each candidate factor by defect lift versus baseline and screen out high-coverage / low-lift factors; prescriptive (`/rai-prescriptive-problem-formulation` + `/rai-prescriptive-results-interpretation`) to solve a minimal set-cover diagnosis and explain why it prefers the deep root over its proximate carriers.

### 5. Trace genealogy backward

**Prompt**

```
/rai-graph-analysis Link each finished unit to every material lot it consumed anywhere upstream — not only the top-tier lots it consumed directly, but all transitive inputs beneath them through the lot genealogy. We need the full set of upstream lots reachable from each unit, so a contaminated component lot several tiers down is attributed to every finished unit that carries it.
```

**Response**

A directed parent -> child genealogy graph on `Lot` (105 nodes, 162 edges); `reachable(full=True)` closes it transitively, and `Unit.touches_lot` links each unit to its directly-consumed lots plus everything reachable beneath them. A unified `Factor.touches` incidence (57,133 facts) puts lots, machines, and shifts on the same footing. Ranking factors by the RAW count of defective units touched is uninformative — the top six are a near-universal raw-material lot (`RM-POLY-L01`, touches all 2,500 units / 142 defects), the housing lot `CP-HOUS-L01` (126), and the busiest placement line `SMT-01` (98): all high-volume, none a cause.

### 6. Contrast-score the candidate factors

**Prompt**

```
/rai-rules-authoring Score each candidate factor by how concentrated defects are among the units it touches. Define lift as the factor's defect rate — defective units touched divided by units touched — divided by the plant-wide baseline failure rate (5.68%). Flag a factor as a suspect when its lift is at least 1.5, it touches at least 30 units, and at least 5 of those are defective, so a near-universal lot or the busiest machine — high coverage but baseline lift — is screened out.
```

**Response**

Derived `Factor.touched_count`, `Factor.defect_count`, `Factor.defect_rate`, and `Factor.lift`; `Factor.is_suspect` fires on 10 factors. Contrast inverts the raw ranking: the trunk factors (lift ≈ 1.0) drop out, and the suspects are led by three populated-board lots `SA-PCBA-L05/L09/L15` (lift 4.9 / 4.9 / 3.0), the solder-paste lot `SP-0423` (lift 4.2, 258 units / 62 defects), reflow oven `REF-02` (lift 2.2, 593 / 73), and a few correlated bystanders (`CP-SOC-L04`, `RM-SI-L03`, both 226 / 29).

### 7. Solve the minimal diagnosis

**Prompt**

```
/rai-prescriptive-problem-formulation From the suspect factors, find the smallest, most specific set that together explains the defective units. Name as few factors as possible — each named factor carries a fixed cost — and penalize naming a factor that also touches many good (non-defective) units. Allow a defective unit to be left unexplained at a cost rather than forcing in a spurious cause. Every defective unit must be explained by a named factor it touches, or marked unexplained.
```

**Response**

Status OPTIMAL, objective 46.32 (24.32 in factor-selection cost plus 22 unexplained defects). The diagnosis names 2 factors — solder-paste lot `SP-0423` and reflow oven `REF-02` — together explaining 120 of 142 defective units (85% coverage). The parsimony cost makes the optimizer prefer the single deep paste lot over the three populated-board lots that carry it (one factor covers all of their defects), and the collateral penalty plus coverage logic leaves the correlated bystanders (`CP-SOC-L04`, `RM-SI-L03`) and the 22 unexplained failures out of the diagnosis. The two named factors are robust to the exact weight values — what drives the result is parsimony plus the good-unit penalty, not the specific costs.

### 8. Interpret the diagnosis

**Prompt**

```
/rai-prescriptive-results-interpretation What is the final diagnosis — which factors, how many defects do they explain, and what evidence supports each? Why did the optimizer name the solder-paste lot rather than the three populated-board lots that scored higher on lift?
```

**Response**

Two root causes explain 85% of the failures, each with corroborating evidence: `SP-0423` (a contaminated solder-paste lot from supplier Meridian Components — 84% of its failures are `COLD_SOLDER`, the paste signature, and it was received 2026-02-09, the exact week-2 onset) and `REF-02` (a reflow oven — 81% `SOLDER_BRIDGE`, and 168 days past calibration, far beyond its peers). The three `SA-PCBA` board lots score higher on raw lift only because every unit on them carries `SP-0423`; backward reachability plus parsimony collapse them into the single upstream lot that actually explains them. The 22 unexplained defects are mostly week-1 failures present *before* the incident — correctly outside the diagnosis. The diagnosis is the prioritized hypothesis; the signature, receipt-date alignment, and calibration age are the evidence an engineer confirms physically.

### 9. Persist the diagnosis into the ontology

**Prompt**

```
/rai-ontology-design Materialize the diagnosis as queryable ontology: a DiagnosisResult singleton holding the defective-unit count, units explained, coverage, and number of root causes, and mark the named factors on Factor.is_root_cause.
```

**Response**

Ontology gains a singleton `DiagnosisResult` with `n_defective` (142), `n_explained` (120), `n_root_causes` (2), and `coverage` (0.85), plus the `Factor.is_root_cause` flag on `SP-0423` and `REF-02`. The headline diagnosis is queryable as ontology, not just stdout.

## Data

Bundled CSVs in `data/`: 20 SKUs across four tiers, 26 bill-of-materials edges, 8 suppliers, 10 machines, 105 lots, 162 lot-genealogy edges, 2,500 units (142 defective) stamped with build week, 10,000 unit-to-lot consumption rows, 10,000 unit-process rows, and 118 candidate factors. `generate_data.py` regenerates them deterministically from a seed, with two planted root causes that share a week-2 incident onset (contaminated paste lot `SP-0423`, received at the onset; reflow oven `REF-02`, drifting at the onset) and several decoys (a near-universal housing lot, a high-volume placement line, the day shift). Contaminated boards reach only units built on or after the onset, so the timeline is a real signal. All stages run end-to-end via `defect_root_cause.py`.
