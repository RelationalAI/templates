# Cross-Template Cleanup Plan

Branch: `worktree-cross-template-cleanup`
Scope: `v1/` templates portfolio
Goal: fix per-template defects, consolidate redundancy without losing unique patterns, fill domain/reasoner gaps.

---

## 0. Status snapshot

- 33 templates in `v1/` (excluding `README.md`)
- Reasoner mix: 17 prescriptive (pure), 7 graph (pure), 1 rules, 0 standalone predictive, 6 multi-reasoner, 1 querying starter, 1 scaffold
- Industry mix: heavy supply chain (11), manufacturing (5), retail (2); zero coverage in telco, insurance, pharma, aviation, public sector (broadly)

Two sources of customer friction:
1. Within-template defects (script structure, README placeholders, docstring gaps)
2. Cross-template redundancy in supply chain + prescriptive; under-representation of predictive + rules

---

## 1. Within-template cleanup

Batch by defect class to minimize churn.

### Wave 1 — script structure (mechanical fix)

Templates: `ad_spend_allocation`, `diet`, `factory_production`, `traveling_salesman`, `warehouse_allocation`, `water_allocation`, `supplier_reliability`, `demand_planning_temporal`, `hospital_staffing`, `order_fulfillment`, `production_planning`, `supply_chain_transport`

Fixes:
- Insert `# Configure inputs` section at top with `DATA_DIR`, pandas options; before any `Model(...)` call
- Move `Model(...)` to start of `# Define semantic model & load data` section
- Standardize on uppercase `DATA_DIR`
- Single pandas import: drop `import pandas as pd`, keep `from pandas import read_csv` (touches `demand_planning_temporal:34-35`, `energy_grid_planning:37`)

Verification: `python -m py_compile` on each, `ruff check v1/`, eyeball-diff for behavior preservation.

### Wave 2 — README defects

Bold reasoning-type opener (`**Prescriptive**`, `**Graph**`, etc.) in: `diet`, `supplier_reliability`, `retail_markdown`, `shift_assignment`, `sprint_scheduling`, `test_data_generation`, `rai-agent-scaffold`.

Quickstart bash blocks repaired:
- `humanitarian-aid-supply-chain/README.md:81-83` (critical — Quickstart never reaches "Run the template")
- `disease-outbreak-prevention/README.md:81`

Docstring `Output:` section added: `bom-reachability`, `site-centrality-network`, `supplier-impact-analysis`.

Fix `warehouse_allocation.py:1-26` docstring indentation (`Run:`/`Output:` indented 4 spaces inside docstring).

Standardize download URL to `https://docs.relational.ai/...` (touches `warehouse_allocation`, `water_allocation`).

Standardize YAML front matter to 2-space indent (touches `portfolio_balancing`).

Add language tags (`python`, `bash`, `text`) to all fenced blocks across READMEs.

### Wave 3 — pyproject

- `disease-outbreak-prevention/pyproject.toml`: rename package to `rai-template-disease-outbreak-prevention`
- `test_data_generation/pyproject.toml`: add `pandas` to dependencies
- Re-audit imports vs deps across all 33 templates

### Wave 4 — minor

- Remove unused `select` import in `site-centrality-network/site_centrality.py:21`

### Verification gate

After each wave: `python -m py_compile` on every `.py`, `ruff check v1/`, behavior-preservation diff review.

---

## 2. Cross-template consolidation

Goal: fewer templates, same set of unique patterns. Triage:

### Keep as-is — each carries a unique pattern

| Template | Unique pattern preserved |
|---|---|
| `traveling_salesman` | MTZ subtour elimination |
| `supply_chain_transport` | TL/LTL piecewise mode selection |
| `supplier_reliability` | Reliability/cost tradeoff with scenario |
| `supply_chain_resilience` | Multi-reasoner with re-solvable scenarios |
| `bom-reachability` | Transitive closure on bipartite BOM |
| `warehouse_allocation` | Centrality → MILP chained reasoners |
| `humanitarian-aid-supply-chain` | PageRank in public-sector context |
| `diet` | Canonical LP intro |
| `water_allocation` | Nonlinear (Ipopt) solver showcase |
| `hospital_staffing` | Epsilon-constraint bi-objective |
| `retail_markdown` | Price ladder + cumulative inventory |

### Merge / retire

1. **Retire `site-centrality-network`** → fold bridge-detection + WCC into `warehouse_allocation` as additional analysis stages. *Loss: none — patterns absorbed.*
2. **Retire `supplier-impact-analysis`** → fold multi-hop reachability into `supply_chain_resilience` as Stage 0 (blast-radius pre-analysis before MILP). Strengthens multi-reasoner narrative. *Loss: none — pattern absorbed and elevated.*
3. **Merge `inventory_rebalancing` + `order_fulfillment` → `network_flow_planning`**: combine fixed-cost facility opening AND multi-tier flow conservation in one model. Each constraint a clearly-labeled subsection so customers can fork either pattern. *Loss: redundant intros; both constraint shapes preserved.*
4. **Reposition `factory_production`** as the explicit "first prescriptive template" (5-minute intro). Cross-link in `v1/README.md` as a learning ladder: `factory_production` → `production_planning` → `demand_planning_temporal`.

Net effect: 11 supply chain → 8; 17 prescriptive → 15. No unique pattern lost; multi-reasoner story strengthened.

### Index restructuring

Replace alphabetical `v1/README.md` table with a navigation matrix:
- Group by reasoner family (Querying / Graph / Rules / Predictive / Prescriptive / Multi-reasoner)
- Within each group, mark beginner / intermediate / advanced
- Add "Where do I start?" table: customer question → recommended template

---

## 3. Net-new templates for gaps

### 3a. Predictive (currently 0 standalone)

Three predictive templates covering three verticals and three problem shapes:

| Template | Vertical | Problem shape | Data source |
|---|---|---|---|
| `demand_forecasting_favorita` | Retail / CPG | Time-series regression | Kaggle: Favorita Grocery Sales Forecasting |
| `predictive_maintenance_rul` | Manufacturing / Aviation | Sensor time-series → RUL regression or classification | NASA CMAPSS (public domain) |
| `telco_churn` | Telco | Tabular classification | Eval CSV ontology (DEMO_TELCO.RAW) |

**`demand_forecasting_favorita`** — daily SKU × store sales for Ecuadorian grocery chain. Exercises calendar features (holidays, paydays, oil prices), promotions, store/cluster hierarchy. Distinct from `retail_planning`'s in-house GNN: this is tabular-features predictive on real retail data. Bundling: ship a curated subsample (1 store × 30 SKUs × 2 years) plus a download script for the full set.

**`predictive_maintenance_rul`** — NASA turbofan engine degradation. Predict Remaining Useful Life (RUL) per engine from sensor time-series, or classify "fail within next N cycles". Bundling: ship FD001 subset directly. Distinct from `machine_maintenance` (multi-reasoner, simulated failure probabilities) — this is sensor-driven RUL regression as a focused predictive intro.

**`telco_churn`** — DEMO_TELCO.RAW dataset has subscriber + billing + contract + call-pattern features. Tabular classifier predicting next-quarter churn. Pairs with `telco_multi_reasoner` (below).

**Open considerations**:
- Favorita licensing: verify Kaggle redistribution terms before deciding to bundle data vs ship download script
- Modeling approach: Favorita and CMAPSS likely tabular (gradient boosting style) rather than GNN; telco_churn could go either way

### 3b. Rules (currently 1: `shipment_compliance`)

| Template | Vertical | Pattern |
|---|---|---|
| `insurance_underwriting_rules` | Insurance | Eligibility + risk-tier classification, hierarchical entities |

Recommended scope: **auto insurance**, **scope (b) — eligibility flags + risk-tier classification (preferred / standard / non-standard / decline)**, **hierarchical** (applicant → policy → driver(s) → vehicle(s)).

Distinct from `shipment_compliance` (mostly flat flag derivation). Hierarchical structure exercises more PyRel relationship traversal patterns.

### 3c. Telco (currently 0 templates)

Harvested from `rai-agent-evals/reasoner_workflow_evals/eval_qas/Reasoner eval Q&As - 2026-04-10.csv` (DEMO_TELCO.RAW rows 22-31):

| Template | Reasoner | Pattern source (eval row) |
|---|---|---|
| `telco_churn` | Predictive (see 3a) | Row 26 |
| `telco_campaign_budget` | Prescriptive | Rows 30-31 — LP with floor/cap (10%, 3×) + regional cap (50% on WEST). Distinct from `ad_spend_allocation`. |
| `telco_multi_reasoner` (flagship) | Graph + Predictive + Rules + Prescriptive | Rows 27-31 — PageRank on call graph → churn classifier with influence as feature → stop-marketing rule (region+postal overlap) → reallocate budget MILP. Mirrors `fraud-detection`'s shape in a different industry. |

`telco_subscriber_communities` (Louvain on call graph) and `telco_subscriber_influence` (PageRank-style) exist as standalone graph candidates but can be folded into the multi-reasoner instead.

Recommendation: ship `telco_multi_reasoner` (flagship), `telco_campaign_budget`, and `telco_churn`.

### 3d. Other gaps to consider after Phase 1

Not committed yet — flag for future portfolio review:
- Insurance beyond underwriting (claims fraud, reserving)
- Pharma / life sciences (clinical trial recruitment, supply chain for drug distribution)
- Public sector / government (beyond wildlife)
- Aviation / travel (crew scheduling, fleet routing)

---

## 4. Execution order

1. Wave 1 (script structure) — 12 templates, mechanical
2. Wave 2 (README defects) — 9 templates touched
3. Wave 3 (pyproject) — 2-3 templates touched
4. Wave 4 (minor) — 1 template
5. Consolidation: retire `site-centrality-network`, `supplier-impact-analysis`; merge `inventory_rebalancing` + `order_fulfillment`; reposition `factory_production`
6. Index restructuring (`v1/README.md`)
7. Net-new predictive templates: `telco_churn` first (smallest), `predictive_maintenance_rul` second, `demand_forecasting_favorita` third (largest data wrangling)
8. Net-new rules template: `insurance_underwriting_rules`
9. Net-new telco prescriptive + multi-reasoner: `telco_campaign_budget`, `telco_multi_reasoner`

Each phase is a separate logical commit; user handles git merges/pushes per global conventions.

---

## 5. Open questions to resolve before starting net-new work

1. **Favorita licensing**: bundle subsample vs ship download script only?
2. **Predictive modeling approach**: tabular (gradient boosting / linear) or GNN where graph structure exists?
3. **Insurance scope confirmation**: auto, scope (b), hierarchical — or change?
4. **Consolidation green light**: confirm OK to retire `site-centrality-network` and `supplier-impact-analysis` (destructive on git history; patterns folded forward into kept templates).

---

## 6. Risks & mitigations

- **Behavior drift during structural cleanup**: every script must produce identical output post-cleanup. Mitigation: capture baseline output before each wave; diff after.
- **Data licensing on Kaggle datasets**: verify before bundling. Default: download script.
- **Customer disruption from retired templates**: any links from external docs / blog posts to retired templates will 404. Mitigation: keep retired template directories with redirect READMEs pointing to the absorbed-into template.
- **Multi-reasoner template scope creep**: telco_multi_reasoner could balloon. Mitigation: reuse `fraud-detection`'s structure as the cap on complexity.
