# Runbook: (Re)creating this template with the RAI agent skills

This runbook is a recipe for the practitioner who wants to reproduce — or build a new variant of — this four-reasoner chain on top of the bundled demo data. It walks through the same stage-by-stage build the agent followed when authoring `telco_network_recovery.py`, calling out which RAI agent skill governs each step and what each skill adds to the model.

The goal: by the end you should be able to point the same workflow at a different domain (e.g. fleet maintenance, retail demand, energy) and have the agent build a parallel four-stage chain on the same shared-ontology principle.

---

## Inputs you start from

- **Demo data** in `../data/`: 8 CSVs covering 250 cell towers, 1,200 subscribers, 6,000 call-detail records, ~5,000 per-tower performance measurements, 544 equipment / health records, 360 upgrade options, and 3,285 daily-KPI rows × 9 regions. Treat these as a stand-in for the customer's own Snowflake schema.
- **A business question** that no single reasoner answers — here, *"WEST region missed revenue targets and operations look broken; what's the optimal tower-upgrade plan?"*
- **A loaded set of RAI agent skills**: `rai-discovery`, `rai-pyrel-coding`, `rai-rules-authoring`, `rai-graph-analysis`, `rai-prescriptive-problem-formulation`, `rai-prescriptive-results-interpretation`, `rai-ontology-design`.

---

## Step 0 — Scope the question with `rai-discovery`

Before any code, use **`rai-discovery`** to translate the business framing into reasoner choices. The skill classifies the question by reasoner family and tells you which downstream skills to load.

In this case the answer is *all four families plus a descriptive setup query*:

| Sub-question | Reasoner | Why |
|---|---|---|
| "How bad is WEST and is this churn vs. ops?" | Descriptive (queries) | Establishes the situation; no model enrichment needed. |
| "Which towers should we restore?" | Rules | Compound classification on derived per-tower averages. |
| "Whose service breaks if those towers fail?" | Graph | Subscriber-to-subscriber call graph, PageRank for influence, blast-radius aggregation per critical tower. |
| "Is regional demand growing or contracting?" | Predictive (GNN) | Time-series regression on per-region daily KPIs with same-region temporal edges. |
| "What's the optimal upgrade plan?" | Prescriptive (MIP) | Binary tier selection per critical tower, three-factor objective, cost + crew-week constraints. |

Discovery's output is a *plan*, not code: which skill comes next, what each will read from the ontology, and what each will write back. Everything that follows materializes that plan.

---

## Step 1 — Ground the ontology with `rai-ontology-design` and `rai-pyrel-coding`

The chain only needs a focused subset of the broader telco model — 7 concepts, not 18. Drop everything not consumed downstream.

Concepts the chain needs:

- `CellTower` — physical radio site (`region`, `status`, `capacity_gbps`).
- `NetworkPerformance`, `NetworkEquipment`, `EquipmentHealth` — feeds Stage 2 derived averages.
- `Subscriber` + `CallDetailRecord` — feeds Stage 3 PageRank graph.
- `TowerUpgradeOption` — junction with composite identity `(tower_id, tier)` for Stage 4 decision variable.
- `RegionMetric` — composite-key `(metric_date, region)` time-series concept for Stage 1 GNN target.
- `TemporalEdge` — same-region 1-day-lag pairs that drive GNN message passing along time.

Use **`rai-pyrel-coding`** (specifically the data-loading and references sections) to hand each CSV directly into a `Concept.new(...)` call with kwargs for both identity and properties:

```python
src = model.data(cell_towers_df)
model.define(CellTower.new(
    id=src.TOWER_ID,
    name=src.TOWER_NAME,
    capacity_gbps=src.CAPACITY_GBPS,
    status=src.STATUS,
    region=src.REGION,
))
```

For composite-key concepts (`TowerUpgradeOption`, `RegionMetric`, `TemporalEdge`), the same pattern applies — both keys go into `.new()`. The skill's "free-variable scoping" section is essential before you write any aggregations: bare `Concept` symbols inside the same `where(...).require(...)` chain refer to one shared free variable, and FK Properties introduce *separate* anonymous variables unless an outer predicate ties them together. Stage 4's three-factor objective depends on this.

---

## Step 2 — Stage 1, Predictive: GNN regression on `RegionMetric`

No dedicated agent skill in the bundled set covers the predictive reasoner, so this stage follows the working examples in `v1/subscriber_retention/` and `v1/demand_forecasting/` rather than a skill recipe. The shape:

1. Compute lag features in pandas before loading: `prev_day_growth`, `prev_week_growth`, `growth_7d_mean` per region.
2. Compute same-region 1-day-lag pairs as `TemporalEdge` rows.
3. Build `Graph(model, directed=True, weighted=False)` and define `Edge.new(src=src_rm, dst=dst_rm)` joined to `TemporalEdge`.
4. Configure `PropertyTransformer(drop=[date, target], category=[region], continuous=[...12 KPIs + 3 lags...], integer=[counts])`.
5. Train/val/test split temporally (train < Nov 2024, val Nov, test Dec) and load each as a small `*Table` concept tied to `RegionMetric` by composite key.
6. `gnn.fit()` with `task_type="regression"`, `n_epochs=80`, `lr=0.002`, `device="cpu"`.
7. Pull predictions, group by region, compute mean predicted growth → small `RegionGrowth` concept that joins to `CellTower.projected_demand_growth` via region.

The GNN reasoner needs an `EXP_DATABASE` schema where the RAI native app can write training artifacts — see the main README's prerequisites for the one-time DDL.

---

## Step 3 — Stage 2, Rules: derived averages + `is_critical_restore`

Switch to **`rai-rules-authoring`**. The skill's classification table maps each rule to a pattern:

| NL rule | Type | Pattern |
|---|---|---|
| "Average packet loss / latency / error rate per tower" | **Derivation** | `Property` materialized via `aggs.avg(...).where(...).per(CellTower)` |
| "Average equipment health per tower" | **Derivation** | Same pattern, two-hop join `EquipmentHealth → NetworkEquipment → CellTower` |
| "Flag towers needing critical restoration" | **Alerting** | Unary `Relationship` with two `where(...).define(...)` branches (OR semantics via separate calls) |

Two key skill rules apply:
- "Boolean flags must be `Relationship`, not `Property`" → `is_critical_restore` is a unary Relationship.
- "Multi-branch rules accumulate (set-union)" → both branches (DEGRADED + low health, AND high packet loss + low health) call `define(CellTower.is_critical_restore())` separately.

Threshold values are example-specific — `< 0.85` health and `> 5.0` packet loss reflect the demo data's distribution, not a generic rule. The skill's "data exploration before threshold selection" step says to confirm thresholds against the actual range; for this demo the critical-tower equipment averages are 0.45–0.81, so `< 0.85` discriminates cleanly.

---

## Step 4 — Stage 3, Graph: PageRank + blast radius

Switch to **`rai-graph-analysis`**. The skill's question-to-algorithm table puts you in the right place:

- Question "who is most influential in the call network?" + directed graph → `pagerank()`
- Construction Pattern 3 (`edge_concept`) — `CallDetailRecord` *is* the edge concept; `caller`/`callee` are the source/destination Relationships.

Two non-obvious points the skill makes explicit:
- `edge_src_relationship` / `edge_dst_relationship` accept only `Relationship` or `Chain`, not `Property` — the call graph would silently produce 0 edges if you used Properties. Verify with `graph.num_edges().inspect()`.
- `aggregator="sum"` is justified here because parallel calls between the same caller/callee pair are real multi-edges. Omit it when you don't expect parallel edges (the warning surfaces real bugs).

PageRank result lands directly on `Subscriber.influence_score` because `node_concept=Subscriber`. The blast-radius aggregation per critical tower is then a derived Property:

```python
model.define(
    CellTower.weighted_impact(
        aggs.sum(Subscriber.influence_score)
        .where(
            CallDetailRecord.routed_through(CellTower),
            CallDetailRecord.caller(Subscriber),
        )
        .per(CellTower)
    )
)
```

The free-variable scoping rule from `rai-pyrel-coding` matters here: bare `CellTower` and bare `Subscriber` are tied together by the inner `.where(...)` predicates, so the aggregation correctly groups by tower with the right caller-set per tower.

---

## Step 5 — Stage 4, Prescriptive: tower-upgrade MIP

Switch to **`rai-prescriptive-problem-formulation`**. The skill's workflow is:

1. **Variables** — binary `TowerUpgradeOption.selected`, scoped via `where=[TowerUpgradeOption.for_tower(CellTower), CellTower.is_critical_restore()]`. The scope predicates use Stage 2's flag, so the decision space is exactly the (critical tower × tier) cross-product.
2. **Constraints** — three from this problem's structure:
   - At-most-one tier per tower: `aggs.sum(selected).per(CellTower) <= 1`
   - Cost cap: `aggs.sum(selected * cost) <= BUDGET_USD`
   - Install crew-weeks cap: `aggs.sum(selected * install_weeks) <= INSTALL_WEEKS_BUDGET`
3. **Objective** — three-factor product where each factor comes from a different reasoner upstream:

   ```python
   problem.maximize(
       aggs.sum(
           TowerUpgradeOption.selected
           * TowerUpgradeOption.capacity_increase_gbps
           * CellTower.weighted_impact            # Stage 3 (graph)
           * CellTower.projected_demand_growth   # Stage 1 (GNN)
       ).where(
           TowerUpgradeOption.for_tower(CellTower),
           CellTower.is_critical_restore(),       # Stage 2 (rules)
       )
   )
   ```

The skill's pre-solver audit gates apply:
- **Trivial-solution gate** — what if every variable is 0? All constraints satisfied, but objective = 0 (worst for `maximize`), so the solver pushes off the floor. Safe.
- **Feasibility precheck** — at least one BRONZE option per critical tower fits within $5M; verify by aggregating the cheapest tier across critical towers in pandas before solving.
- **Coefficient presence** — every objective coefficient (`capacity_increase_gbps`, `weighted_impact`, `projected_demand_growth`) must be populated. If any are unbound, the solver returns OPTIMAL with a vacuous objective. Spot-check with `model.select(coef_prop).to_df()` before solve.

`problem.solve(solver="gurobi")` returns OPTIMAL: `$4,956,843` plan, 122 Gbps restored, 12 GOLD + 2 SILVER + 1 BRONZE, all 15 critical WEST towers covered, install crew-weeks = 164 of 200 (slack).

---

## Step 6 — Interpret with `rai-prescriptive-results-interpretation`

After the solve, use the interpretation skill to extract the practitioner-facing summary:

- **Status check** — OPTIMAL, not boundary or infeasible. No surprises.
- **Binding constraints** — cost is binding ($4.96M of $5M); install weeks slack 36. The plan is *budget-bound, not crew-bound* — expanding crews wouldn't help; raising budget would.
- **Sensitivity** — relaxing budget to $6M would let TWR-0009 jump BRONZE → GOLD for ~$380K marginal cost. Worth flagging if the customer might flex capex.
- **Why this tier mix** — GOLD dominates (12/15) because high-blast-radius towers have capacity-uplift coefficients large enough that GOLD beats SILVER even at 4× cost. SILVER/BRONZE land on the lowest-influence towers where the optimizer buys cheaper tiers to free budget for the GOLDs.

---

## Adapting this recipe to a new domain

The chain pattern transfers cleanly. To rebuild for a different problem:

1. Re-run `rai-discovery` on the new business question — does it actually need all four reasoner families, or is one or two sufficient?
2. Strip the demo ontology to the concepts the new chain needs (lean is better for type inference and solver compile time).
3. Stage 1 (GNN) is optional — if there's no time series, skip it and let the prescriptive objective use static coefficients.
4. Stages 2–4 are the load-bearing chain: Rules narrows the decision scope, Graph weights it, Prescriptive picks. The objective's job is to combine the upstream signals with `*` — each factor is a different reasoner's enrichment.
5. Keep the validation checks at every stage: assert flagged-set size, assert PageRank top-N looks plausible, assert the trivial-solution gate, assert objective is not zero.

The shape this template demonstrates — *each reasoner writes a property the next reasoner reads* — is what makes the chain accretive rather than serial. The agent skills are how you reliably author each link.
