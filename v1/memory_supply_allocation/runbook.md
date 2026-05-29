# Runbook: Memory Supply Allocation — Multi-Reasoner Walkthrough

A memory-chip manufacturer must allocate scarce HBM3E and adjacent SKU supply across 11 customers over a 36-month horizon. Capacity is itself a function of 6 named foundries' health and 3 raw-material inputs (helium, neon, palladium); customers sit in a dependency graph where hyperscalers declare willingness to yield part of their allocation so their equipment-maker suppliers stay supplied. As disruptions surface monthly, the planner re-solves the remaining horizon. The chain produces a monthly rolling-horizon allocation plus a dependency-graph cascade analysis (single points of failure, supplier-offline and input-shortage what-ifs).

Prompts below are designed to run in order in a single session, inheriting ontology state. Each downstream prompt reads enrichments written by an earlier stage.

## The chain

```
Ontology: 8 source-data concepts (Customer 11, Product 5, Period 36,
Demand 1,476, Supplier 6, SupplierProductCapacity 360, Input 3,
InputUsage 10) plus Dependency (7), SupplierCapabilityForecast (216),
and the disruption-reveal schedule. The chain produces a 3-step monthly
rolling-horizon allocation plan; total margin erodes from $47.09B
(36-month baseline) to $30.19B (24-month tail after both disruptions),
with hyperscaler customers absorbing the disruption while equipment-
maker customers stay pinned at their elevated floors.

  ─────────────────────────────────────────────────────────────────
  STAGE 1  Rules        ──►  Customer.max_declared_yield_pct  (11)
                              Customer.elevated_floor_pct      (11)
                              Customer.depends_on              (7 edges)
                              Customer.is_dependency_spof      (1: Apex)
  ─────────────────────────────────────────────────────────────────
  STAGE 2  Predictive   ──►  SupplierCapabilityForecast      (216)
                 (regression)  capability_pct per (supplier, month);
                              range 0.93 – 0.99 across the horizon.
  ─────────────────────────────────────────────────────────────────
  STAGE 3  Prescriptive ──►  Demand.x_alloc                  (decisions)
                              EffectiveCapacity (iter-tagged)
                              ScenarioOutcome (3 iterations)
                              iter 0 OPTIMAL · $47.09B · months 1-36
                              iter 1 OPTIMAL · $41.96B · months 5-36
                              iter 2 OPTIMAL · $30.19B · months 13-36
                              Equipment makers pinned; hyperscalers
                              absorb -$2.43B Hyperion / -$2.21B Aether.
  ─────────────────────────────────────────────────────────────────
  STAGE 4  Graph        ──►  9 paths (7 one-hop + 2 two-hop)
            (paths)           Customer.is_dependency_spof query
                              Supplier.offline_impact_cells (6)
                              Input.shortage_impact_cells   (3)
                              Apex SPOF · Orion widest supplier impact
                              (72 cells, 60.9% drop) · Helium widest
                              input impact (180 cells, all 5 SKUs).
  ─────────────────────────────────────────────────────────────────
```

## Workflow

### 1. Build ontology

**Prompt**

```
/rai-build-starter-ontology Build a memory-chip allocation ontology from the CSVs in data/. Include a Dependency junction concept so downstream-to-upstream customer yield declarations can be modeled, plus Supplier, SupplierProductCapacity, Input, and InputUsage concepts so capacity can be composed from supplier capability and raw-material exposure. Also include a SupplierCapabilityForecast concept holding the predicted capability_pct per (supplier, month).
```

**Response**

Concepts created and bound to the bundled CSVs: Customer (11 rows), Product (5 SKUs spanning HBM3E / HBM3 / DDR5 / LPDDR5X / NAND), Period (36 months), Demand (1,476 cells), Supplier (6 foundries), SupplierProductCapacity (360 nominal-capacity rows), Input (3: helium, neon, palladium), InputUsage (10 intensity rows), Dependency (7 yield declarations), SupplierCapabilityForecast (216 forecast rows). Junction concepts use composite identify_by so the foreign keys are explicit.

### 2. Examine ontology

**Prompt**

```
/rai-querying What concepts and relationships does the ontology have, how many rows are in each, and what is the customer-customer dependency landscape: how many customers declare yield to an upstream supplier, how many are protected by an elevated floor, and is there any multi-hop chaining?
```

**Response**

11 source-data concepts including the predictive `SupplierCapabilityForecast` and the 7-row `Dependency` junction. 4 customers declare outgoing yields (Hyperion 10%, Aether 8%, Helios 5%, Astra 3%); 4 customers carry an elevated floor above their base (Photonic Lithography 0.95, Vertex Test Systems 0.92, Crystal Wafer Tools 0.90, Apex Photonic Components 0.90). One 2-hop chain in the data: Photonic Lithography both receives yield (from Hyperion and Aether) AND declares yield outgoing (to Apex), creating `Hyperion → Photonic → Apex` and `Aether → Photonic → Apex`. Demand totals $147B across the horizon; baseline effective capacity totals $125B — HBM3E is the structurally binding SKU.

### 3. Discover reasoner chain

**Prompt**

```
/rai-discovery We have to allocate scarce memory-chip supply across 11 customers over 36 monthly periods, with capacity that depends on 6 named foundries (modulated by predicted capability) and 3 raw-material inputs. Customers in the dependency graph yield part of their allocation so their equipment suppliers stay supplied. Disruptions surface over the horizon — a supplier outage and a helium shortage. Which RAI reasoners do we need, in what order, to land on a defensible monthly rolling-horizon plan AND explain who absorbs each disruption when it surfaces?
```

**Response**

Four-reasoner chain on the shared ontology. **Rules** (`/rai-rules-authoring`) to derive per-customer max_declared_yield_pct + elevated_floor_pct + a single-point-of-failure flag from the Dependency junction. **Predictive** (`/rai-predictive-modeling` or pre-computed table) to provide a SupplierCapabilityForecast per (supplier, month). **Prescriptive** (`/rai-prescriptive-problem-formulation`) to solve revenue-max LP as a rolling horizon — baseline plus one re-solve per disruption reveal, with effective capacity recomputed against the current forecast and input-availability state each time. **Graph** (`/rai-graph-analysis` with the paths library) to enumerate variable-length customer dependency chains, flag the dependency SPOF, and run two cascade what-if branches (supplier-offline, input-shortage).

### 4. Derive customer yield, elevated floor, and SPOF flag

**Prompt**

```
/rai-rules-authoring Which customers should be flagged as yielding-downstream (willing to give up part of their allocation to keep an upstream supplier covered), which carry an elevated service floor above their base, and which are dependency single points of failure? A customer is a dependency single point of failure when (a) exactly one incoming dependency lifts its floor above its base, and (b) that floor would drop back to base if the single protecting edge were removed.
```

**Response**

`Customer.max_declared_yield_pct`, `Customer.elevated_floor_pct`, `Customer.has_elevated_floor`, `Customer.n_incoming_dependencies`, and `Customer.is_dependency_spof` derived properties bound to the ontology. 4 customers declare yield (Hyperion 10%, Aether 8%, Helios 5%, Astra 3%). 4 customers carry elevated floors (Photonic 0.95, Vertex 0.92, Crystal 0.90, Apex 0.90). Exactly 1 customer is a dependency SPOF: Apex Photonic Components, protected only by the Photonic → Apex edge.

### 5. Bind supplier capability forecast as ontology

**Prompt**

```
/rai-predictive-modeling Bind the supplier_capability_forecast.csv table as a SupplierCapabilityForecast concept — one capability_pct prediction per (supplier, month) over the 36-month horizon — so the prescriptive LP can use it directly. The CSV ships pre-computed; in production this would be a node-classification GNN on Supplier whose features include recent on-time-rate, equipment age, and geopolitical exposure score. Report per-supplier mean and range so a planner can sanity-check the forecast distribution.
```

**Response**

`SupplierCapabilityForecast` concept loaded (216 rows = 6 suppliers × 36 months). Per-supplier mean capability_pct ranges 0.95–0.97 across suppliers; min 0.93, max 0.99 across all (supplier, month) cells. The structure is GNN-ready — replace the CSV load with predictions from `/rai-predictive-modeling` and rebind to the same Concept with no downstream changes.

### 6. Solve baseline allocation across the full horizon

**Prompt**

```
/rai-prescriptive-problem-formulation What is the revenue-maximizing 36-month monthly allocation of supply across customers, subject to: (1) capacity per (product, month) computed as the sum over suppliers of nominal_capacity_usd × capability_pct, scaled by the product across raw-material inputs of (1 − intensity × (1 − input_availability)); (2) per-cell upper bound of (1 − max_declared_yield_pct) × demand_usd; (3) per-cell lower bound of max(base_service_floor_pct, elevated_floor_pct) × demand_usd. Solve under baseline forecast with no disruption applied. Report total margin and per-customer service level (alloc / demand aggregated per customer over the horizon).
```

**Response**

OPTIMAL · margin $47,089,150,341 over months 1–36 · binding constraint is HBM3E capacity. Equipment-maker customers run at their elevated floors: Photonic Lithography 95.0%, Vertex Test Systems 98.8%, Crystal Wafer Tools 98.2%, Apex Photonic Components 97.5%. Hyperscalers run below 100% under HBM3E scarcity: Hyperion 76.0%, Aether 83.7%, Helios 83.5%. ScenarioOutcome with iter_id=0 persists the headline.

### 7. Apply disruption reveals and re-solve rolling horizon

**Prompt**

```
/rai-prescriptive-problem-formulation Replan as each disruption surfaces. At month 5, Orion Foundry capability_pct drops to 0.78 for months 5–10 (unscheduled EUV tool downtime). At month 13, helium availability drops to 0.80 for months 13–18 (geopolitical event). For each reveal, update effective capacity and re-solve over the remaining months under the same three constraint types from the baseline solve. Report the cumulative plan diff at the customer level vs the prior iteration's allocation over the overlapping months.
```

**Response**

Two additional OPTIMAL solves: iter_id=1 (months 5–36) margin $41,960,554,872; iter_id=2 (months 13–36) margin $30,188,075,056. Plan-diff iter 0 → iter 1 (months 5–36): Aether −$369.62M, Hyperion −$280.36M, Beacon −$27.10M, Helios −$11.94M, equipment makers $0 (pinned to elevated floor). Plan-diff iter 1 → iter 2 (months 13–36): Hyperion −$2,149.37M, Aether −$1,839.17M, Helios −$553.37M, Beacon −$367.45M, equipment makers still $0. Hyperscalers absorb the entire disruption surface.

### 8. Enumerate dependency chains and confirm the SPOF

**Prompt**

```
/rai-graph-analysis Using the paths library, enumerate every 1- to 3-hop chain through the Customer.depends_on graph. Which customer endpoints have the most paths terminating at them (the most redundant protection), and which customer is structurally a single point of failure — the only customer whose elevated floor depends on exactly one direct incoming dependency edge AND has no alternative-path protection?
```

**Response**

9 total paths via `model.path(Customer.depends_on.repeat(1, 3)).all_paths()`: 7 one-hop and 2 two-hop. Multi-hop chains: `Hyperion → Photonic → Apex` and `Aether → Photonic → Apex`. Photonic Lithography has 2 paths terminating, Vertex and Crystal each have 2, and Apex has 3 (1 direct + 2 indirect through Photonic). Despite Apex's higher terminating-path count, it is still the lone dependency SPOF — `model.where(Customer.is_dependency_spof()).select(Customer.name).to_df()` returns Apex Photonic Components as the only row. The indirect paths through Photonic protect Apex only as long as the direct Photonic → Apex edge stands; removing that edge drops Apex's effective floor from 0.90 back to its 0.70 base.

### 9. What-if: supplier offline and input shortage

**Prompt**

```
/rai-graph-analysis For each supplier, recompute effective capacity with that supplier's capability_pct forced to 0 across all 36 months and count the (product, period) cells whose capacity drops more than 10% vs the baseline forecast. Do the same for each raw-material input by forcing its availability to 0.30 and counting cells whose drop exceeds 5%. Which single supplier and which single input cast the widest cascade footprint? Persist the per-supplier and per-input cell counts back to the ontology so a downstream analyst can query the risk ranking without re-running the cascade.
```

**Response**

Widest supplier impact: Orion Foundry — 72 cells affected, max 60.9% capacity drop across HBM3E + HBM3 (Nimbus Foundry and Pelican Memory Works also at 72 cells but with different SKU mixes and 70.5% / 70.9% max drops). Widest input impact: Helium — 180 cells across all 5 SKUs (HBM3E avg −35%, HBM3 −28%, DDR5 −18%, LPDDR5X −10%, NAND −7%). `Supplier.offline_impact_cells`, `Supplier.offline_max_cap_drop_pct`, and `Input.shortage_impact_cells` are now ontology-resident — `model.where(Supplier.offline_impact_cells > 50).select(Supplier.name).to_df()` returns the high-impact suppliers.

### 10. Interpret the plan

**Prompt**

```
/rai-prescriptive-results-interpretation Summarize the rolling-horizon outcome: who absorbs the disruption, what protects the equipment-maker customers, and how does the margin evolve across the three iterations? Highlight the structural risk visible in the supplier-offline and input-shortage cascade rankings.
```

**Response**

Equipment-maker customers (Photonic Lithography, Vertex Test Systems, Crystal Wafer Tools, Apex Photonic Components) stay pinned at their elevated floors (88–95%) across all three iterations — protected by the dependency mechanic the hyperscalers have declared. Hyperscalers absorb the entire disruption surface: Hyperion takes a cumulative −$2.43B vs the baseline plan, Aether −$2.21B. The 36-month-baseline-to-24-month-tail margin headline is $47.09B → $30.19B (the $16.9B gap mixes disruption impact with the shorter remaining horizon). Structural risk surfaced by Stage 4: Apex is a single point of failure on the customer dependency graph; Orion Foundry is the single supplier whose outage casts the highest-magnitude shadow on HBM3E; Helium is the single input with the broadest cross-SKU exposure.

## Data

Bundled CSVs in `data/`: 11 customers (3 hyperscalers, 1 consumer OEM, 1 automotive, 1 industrial, 4 foundry-equipment makers, 1 distributor — service floors 0.45 to 0.75), 5 chip SKUs (HBM3E / HBM3 / DDR5 / LPDDR5X / NAND with margin 0.18–0.55), 36 monthly periods spanning 2026-01 to 2028-12, 1,476 demand cells (customer × SKU × month, USD), 6 named foundries (Orion / Helios / Nimbus / Pelican / Stellar / Vega), 360 supplier-product-month nominal capacities, 3 raw-material inputs (Helium / Neon / Palladium), 10 input-usage intensities, 216 supplier-capability forecasts (capability_pct ∈ [0.91, 0.99]), 7 dependency declarations (yield 0.03–0.10, elevated floor 0.88–0.95), 2 disruption-reveal rows (Orion at month 5, helium at month 13). The data generator `dev_temp/gen_memory_alloc_data_v2.py` regenerates the CSVs deterministically from a seed and prints a baseline-feasibility precheck. All four chain stages run end-to-end via `memory_supply_allocation.py`.
