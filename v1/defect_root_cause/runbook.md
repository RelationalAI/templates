# Runbook: Defect Root-Cause Analysis — Multi-Reasoner Walkthrough

Final-test failures on a consumer-electronics assembly line have jumped from a ~1.2% baseline to 6.3% over three weeks. Every serialized unit carries its full material genealogy (which lots it consumed, transitively, through a four-tier bill of materials) and its process history (which machine and shift ran each operation). The chain works backward from the failures to the smallest, most specific set of root causes — resisting the pull of high-volume factors that merely touch everything.

> **Headline figures below** are from a real Snowflake-backed run of `defect_root_cause.py`. The corpus and all three reasoners are deterministic (the data is seeded; graph reachability, contrast scoring, and the set-cover MILP are exact), so the figures reproduce run-to-run. See the template README's *Customize this template* for the contrast thresholds and objective-weight knobs.

## The chain

```
Ontology: 6 source-data concepts (SKU, BillOfMaterials, Supplier, Machine, Lot,
Unit) plus unit-lot consumption, unit process history, and a Factor candidate
set. 2,500 units (157 defective, 6.28%), 105 lots, 162 genealogy edges,
118 candidate factors. The chain produces a minimal root-cause diagnosis.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Graph        ──►  Unit.touches_lot  (57,142 incidence facts)
   /rai-graph-analysis       Transitive backward reachability over the
                             105-lot / 162-edge parent->child genealogy.
                             Raw defect counts rank trunk lots first.
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Rules        ──►  Factor.lift, Factor.is_suspect  (9 suspects)
   /rai-rules-authoring      Defect lift vs. the 6.28% baseline; screens
                             out high-coverage / low-lift trunk factors.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Prescriptive ──►  Factor.is_root_cause (2), DiagnosisResult
   /rai-prescriptive-        OPTIMAL · obj 42.0 · {SP-0423, REF-02}
   problem-formulation       explain 141/157 defects (90% coverage).
  ─────────────────────────────────────────────────────────────────
```

## Workflow

> **How to use this walkthrough.** Each section below is a Prompt that an analyst pastes into a fresh agent session loaded with the named `/rai-*` skill. Prompts are designed to run **in order, in a single session** — every step relies on enrichments the previous steps wrote back to the shared ontology, so the agent inherits accumulated model state across prompts.

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a manufacturing genealogy ontology from the CSVs in data/. Model finished Units with their final-test result, the multi-tier SKU bill of materials, material Lots with a parent->child genealogy (a built lot consumes its input lots), each unit's directly-consumed lots and its process history (machine and shift per operation), and a Factor concept enumerating the candidate root causes — every lot, machine, and shift.
```

**Response**

Concepts bound to the bundled CSVs: `SKU` (20, four tiers), `BillOfMaterials` (26 edges), `Supplier` (8), `Machine` (10, with `calibration_age_days`), `Lot` (105, with a self-referencing `consumes` genealogy relationship), `Unit` (2,500, with `defective` / `defect_type` / `shift` and `consumes_lot` + `ran_on` relationships), and `Factor` (118 candidates with per-kind back-pointers to a lot, machine, or shift). Genealogy edges total 162.

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, how many rows are in each, and what is the current final-test failure picture — how many units are defective, what failure rate is that, and what is the defect-type mix?
```

**Response**

2,500 `Unit` rows, 157 defective — a 6.28% final-test failure rate, up from the ~1.2% baseline. Defect-type mix: `COLD_SOLDER` 71, `SOLDER_BRIDGE` 67, `MISSING_COMPONENT` 9, `TOMBSTONE` 6, `MISALIGNMENT` 4. The two dominant signatures (cold solder, solder bridge) hint at a paste/placement issue and a thermal/reflow issue respectively. Supporting concepts: 105 `Lot`, 162 genealogy edges, 118 candidate `Factor` rows (105 lots + 10 machines + 3 shifts).

### 3. Discover reasoner questions

**Prompt**

```
/rai-discovery Final-test failures jumped from ~1.2% to 6.3% over three weeks. Every unit carries its full material genealogy and process history. Which RAI reasoners do we need, in what order, to work backward from the failures to the smallest defensible set of root causes — rather than just a long list of things the bad units have in common?
```

**Response**

Plans the three-reasoner backward chain on the shared ontology: graph (`/rai-graph-analysis`) to close the lot genealogy transitively and attribute every upstream lot to the units that carry it; rules (`/rai-rules-authoring`) to contrast-score each candidate factor by defect lift versus baseline and screen out high-coverage / low-lift factors; prescriptive (`/rai-prescriptive-problem-formulation` + `/rai-prescriptive-results-interpretation`) to solve a minimal set-cover diagnosis and explain why it prefers the deep root over its proximate carriers.

### 4. Trace genealogy backward

**Prompt**

```
/rai-graph-analysis Link each finished unit to every material lot it consumed anywhere upstream — not only the top-tier lots it consumed directly, but all transitive inputs beneath them through the lot genealogy. We need the full set of upstream lots reachable from each unit, so a contaminated component lot several tiers down is attributed to every finished unit that carries it.
```

**Response**

A directed parent -> child genealogy graph on `Lot` (105 nodes, 162 edges); `reachable(full=True)` closes it transitively, and `Unit.touches_lot` links each unit to its directly-consumed lots plus everything reachable beneath them. A unified `Factor.touches` incidence (57,142 facts) puts lots, machines, and shifts on the same footing. Ranking factors by the RAW count of defective units touched is uninformative — the top six are a near-universal raw-material lot (`RM-POLY-L01`, touches all 2,500 units / 157 defects), the housing lot `CP-HOUS-L01` (137), and the busiest placement line `SMT-01` (114): all high-volume, none a cause.

### 5. Contrast-score the candidate factors

**Prompt**

```
/rai-rules-authoring Score each candidate factor by how concentrated defects are among the units it touches. Define lift as the factor's defect rate — defective units touched divided by units touched — divided by the plant-wide baseline failure rate (6.28%). Flag a factor as a suspect when its lift is at least 1.5, it touches at least 30 units, and at least 5 of those are defective, so a near-universal lot or the busiest machine — high coverage but baseline lift — is screened out.
```

**Response**

Derived `Factor.touched_count`, `Factor.defect_count`, `Factor.defect_rate`, and `Factor.lift`; `Factor.is_suspect` fires on 9 factors. Contrast inverts the raw ranking: the trunk factors (lift ≈ 1.0) drop out, and the suspects are led by three populated-board lots `SA-PCBA-L05/L09/L15` (lift 3.7 / 3.5 / 2.8), the solder-paste lot `SP-0423` (lift 3.3, 371 units / 78 defects), reflow oven `REF-02` (lift 2.1, 584 / 77), and a few correlated bystanders (`CP-SOC-L04`, `RM-SI-L03`, both 260 / 37).

### 6. Solve the minimal diagnosis

**Prompt**

```
/rai-prescriptive-problem-formulation From the suspect factors, find the smallest, most specific set that together explains the defective units. Name as few factors as possible — each named factor carries a fixed cost — and penalize naming a factor that also touches many good (non-defective) units. Allow a defective unit to be left unexplained at a cost rather than forcing in a spurious cause. Every defective unit must be explained by a named factor it touches, or marked unexplained.
```

**Response**

Status OPTIMAL, objective 42.0 (26.0 in factor-selection cost plus 16 unexplained baseline defects). The diagnosis names 2 factors — solder-paste lot `SP-0423` and reflow oven `REF-02` — together explaining 141 of 157 defective units (90% coverage). The parsimony cost makes the optimizer prefer the single deep paste lot over the three populated-board lots that carry it (one factor covers all of their defects), and the collateral penalty plus coverage logic leaves the correlated bystanders (`CP-SOC-L04`, `RM-SI-L03`) and the 16 scattered baseline failures out of the diagnosis. The two named factors are robust to the exact weight values — what drives the result is parsimony plus the good-unit penalty, not the specific costs.

### 7. Interpret the diagnosis

**Prompt**

```
/rai-prescriptive-results-interpretation What is the final diagnosis — which factors, how many defects do they explain, and how should we read it? Why did the optimizer name the solder-paste lot rather than the three populated-board lots that scored higher on lift?
```

**Response**

Two root causes explain 90% of the failures, each reported with corroborating evidence: `SP-0423` (a contaminated solder-paste lot from supplier Meridian Components — 87% of its failures are `COLD_SOLDER`, the paste signature) and `REF-02` (a reflow oven — 84% `SOLDER_BRIDGE`, and 168 days past calibration, far beyond its peers). The three `SA-PCBA` board lots score higher on raw lift only because every unit on them carries `SP-0423`; backward reachability plus parsimony collapse them into the single upstream lot that actually explains them. The 16 unexplained defects are scattered baseline failures with no shared suspect — correctly left rather than over-fit. The diagnosis is the prioritized hypothesis; the signature, supplier/receipt date, and calibration age are the evidence an engineer confirms physically.

### 8. Persist the diagnosis into the ontology

**Prompt**

```
/rai-ontology-design Materialize the diagnosis as queryable ontology: a DiagnosisResult singleton holding the defective-unit count, units explained, coverage, and number of root causes, and mark the named factors on Factor.is_root_cause.
```

**Response**

Ontology gains a singleton `DiagnosisResult` with `n_defective` (157), `n_explained` (141), `n_root_causes` (2), and `coverage` (0.90), plus the `Factor.is_root_cause` flag on `SP-0423` and `REF-02`. The headline diagnosis is queryable as ontology, not just stdout.

## Data

Bundled CSVs in `data/`: 20 SKUs across four tiers, 26 bill-of-materials edges, 8 suppliers, 10 machines, 105 lots, 162 lot-genealogy edges, 2,500 units (157 defective), 10,000 unit-to-lot consumption rows, 10,000 unit-process rows, and 118 candidate factors. `generate_data.py` regenerates them deterministically from a seed, with two planted root causes (contaminated paste lot `SP-0423`; drifted reflow oven `REF-02`) and several decoys (a near-universal housing lot, a high-volume placement line, the day shift). All three chain stages run end-to-end via `defect_root_cause.py`.
