# RelationalAI Templates

This repository contains runnable RelationalAI templates that demonstrate end-to-end solution patterns across optimization, graph analytics, fraud detection, supply chain planning, and other decision intelligence workflows.

Each template lives in its own folder with code, sample data, and a template-specific README. Templates are grouped into versioned directories so the repository can support multiple generations of examples side by side.

## Templates

Within a template folder, you will usually find:

- `README.md` with the problem statement, prerequisites, and run instructions
- `pyproject.toml` for template-local dependencies
- a main runner such as `<template>.py` or a notebook
- `data/` containing sample input data when the template uses local files
- `runbook.md` with ordered prompts to recreate or adapt the template using a coding agent with RelationalAI skills (multi-reasoner templates)

The index below covers the current (`v1`) templates, grouped by industry. Expand an industry to see its templates, the reasoners each uses, and a one-line description. Older templates remain under [`v0.13/`](v0.13/) and [`v0.14/`](v0.14/) for reference; use `v1` for new development.

<!-- BEGIN TEMPLATE INDEX -->

<details>
<summary>Cross-Industry (4)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [rai-agent-scaffold](v1/rai-agent-scaffold/) | Graph | Scaffold for packaging a RelationalAI semantic model as a Snowflake Cortex agent and exposing it through Snowflake Intelligence. |
| [shift_assignment](v1/shift_assignment/) | Prescriptive | Assign workers to shifts based on availability to meet coverage requirements. |
| [simple-start](v1/simple-start/) | Graph | A minimal notebook to connect to Snowflake, model a small graph, and compute betweenness centrality with RelationalAI. |
| [wildlife-conservation-network](v1/wildlife-conservation-network/) | Graph | Use the Louvain community detection algorithm and degree centrality analysis to identify collaboration clusters among wildlife conservation organizations, helping optimize resource sharing and identify key coordination hubs. |

</details>

<details>
<summary>Energy & Utilities (2)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [energy_grid_planning](v1/energy_grid_planning/) | Graph, Rules-based, Prescriptive | Multi-reasoner template: demand forecasting, grid vulnerability analysis, compliance rules, and multi-objective optimization for AI data center interconnection planning on the ERCOT (Texas) grid. |
| [water_allocation](v1/water_allocation/) | Prescriptive | Minimize the cost of distributing water from sources to users with nonlinear transmission losses. |

</details>

<details>
<summary>Financial Services (7)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [commercial_underwriting](v1/commercial_underwriting/) | Rules-based | Run rules-based eligibility checks and risk-tier classification across a four-level commercial property/casualty hierarchy (insured entity, policy, location, coverage). |
| [financial_index_replication](v1/financial_index_replication/) | Prescriptive, Rules-based | Prescriptive optimization template for selecting a sparse 20-stock replication basket and weights that track an S&P 500-like benchmark. |
| [fraud-detection](v1/fraud-detection/) | Graph, Rules-based, Predictive, Prescriptive | Multi-reasoner transaction-fraud pipeline: account PageRank (Graph) + high-volume account flags (Rules) feed a GNN binary classifier (Predictive) whose per-transaction scores drive a knapsack investigator-budget MILP (Prescriptive). |
| [money_laundering_motif_detection](v1/money_laundering_motif_detection/) | Prescriptive | Detect three classes of layering motif on the same transaction ledger, each demonstrating a different CSP technique that rules / paths / graph reasoning alone cannot enforce: per-vertex aggregate equality (butterfly), pairwise distinctness over a chosen subset (smurf army), and cardinality on a chosen subset (KYC-mix burst). |
| [portfolio_balancing](v1/portfolio_balancing/) | Prescriptive, Rules-based, Graph | Multi-reasoner template: rules-based compliance, covariance clustering, and bi-objective Markowitz optimization with a crisis-regime stress test. |
| [synthetic_order_lifecycle](v1/synthetic_order_lifecycle/) | Prescriptive | Generate synthetic order-lifecycle event traces (PLACE / MODIFY / CANCEL / FILL) that satisfy MiFID II / Reg NMS-flavour sequencing rules using a CSP solver. |
| [underwriting_audit](v1/underwriting_audit/) | Prescriptive | Audit an underwriting ruleset against a catalog of properties. For each property, the solver either proves the property holds (PASS) or returns K distinct counterexample applicants who falsify it (FAIL). Multi-property batch audit, CSP solver in multi-solution mode. |

</details>

<details>
<summary>Healthcare & Life Sciences (6)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [diet](v1/diet/) | Prescriptive | Select foods to satisfy nutritional requirements at minimum cost. |
| [disease-outbreak-prevention](v1/disease-outbreak-prevention/) | Graph | Use weighted degree centrality to identify the highest-risk healthcare facilities in a public health network, considering both connection volume and intensity, to prioritize resource deployment during disease outbreaks. |
| [hospital_staffing](v1/hospital_staffing/) | Prescriptive | Explore the tradeoff between overtime cost and patient service level using bi-objective optimization with epsilon constraint. |
| [patient_cohort_recruitment](v1/patient_cohort_recruitment/) | Graph, Rules-based, Prescriptive | Build a clinical-research cohort over a patient knowledge graph: a Graph reasoner closes a kinase-pathway sub-ontology, relational rules lift the closure to per-patient eligibility and coverage facts, and a CSP solver picks K patients whose joint coverage spans enough distinct genes, therapies, and adverse events for the analysis to generalize. |
| [smoker_status_prediction](v1/smoker_status_prediction/) | Predictive | Predict whether a person is a smoker from demographic and medical attributes plus a network of social connections, using a Graph Neural Network. |
| [synthetic_eligibility_records](v1/synthetic_eligibility_records/) | Prescriptive | Generate K distinct, internally consistent member eligibility records per solve using a CSP solver in multi-solution mode: each record satisfies CMS Medicare-eligibility, age-by-plan-type CFDs, and PCP-network attribution. |

</details>

<details>
<summary>Manufacturing (4)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [bom-reachability](v1/bom-reachability/) | Graph | Trace transitive dependencies through a bill of materials to identify which raw materials each finished product depends on and which components are structural bottlenecks. |
| [factory_production](v1/factory_production/) | Prescriptive | Maximize profit from production with limited resource availability per factory. |
| [product_configurator](v1/product_configurator/) | Prescriptive | Enumerate every feasible build of a configurable product using a CSP solver in multi-solution mode: one option per slot subject to feature-model rules, regional regulations, and a price ceiling. |
| [production_planning](v1/production_planning/) | Prescriptive | Schedule production across machines to meet demand and maximize profit with scenario analysis. |

</details>

<details>
<summary>Retail & Consumer (7)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [ad_spend_allocation](v1/ad_spend_allocation/) | Prescriptive | Allocate marketing budget across channels and campaigns to maximize conversions. |
| [book_slate_recommendation](v1/book_slate_recommendation/) | Graph, Prescriptive | Recommend K books per reader and order them by slot, under diversity, freshness, and explainability constraints. |
| [campaign_roi](v1/campaign_roi/) | Prescriptive | Reallocate marketing campaign budgets across regions to maximize conversions, with per-campaign floor and cap constraints and a regional cap on a paused region. |
| [demand_forecasting](v1/demand_forecasting/) | Predictive | Forecast next-period unit sales per (store, item, day) with a regression GNN over a heterogeneous retail knowledge graph: sales transactions linked to stores, items, and item families so the GNN propagates signal through the store and product hierarchies. |
| [planogram_optimization](v1/planogram_optimization/) | Predictive, Prescriptive | Decide integer facing counts per SKU to maximize predicted weekly demand under shelf capacity and category cardinality limits, where per-(SKU, facing_count) demand comes from a regression model. |
| [retail_markdown](v1/retail_markdown/) | Prescriptive | Set discount levels across weeks to maximize revenue while clearing inventory. |
| [retail_planning](v1/retail_planning/) | Predictive, Prescriptive | Predict article sales and customer churn with GNNs, then optimize markdown pricing and inventory planning to maximize revenue and minimize costs. |

</details>

<details>
<summary>Supply Chain & Logistics (9)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [demand_planning_temporal](v1/demand_planning_temporal/) | Prescriptive | Plan weekly production and inventory across sites over a date-filtered planning horizon to minimize total cost while meeting demand. |
| [humanitarian-aid-supply-chain](v1/humanitarian-aid-supply-chain/) | Graph | Use graph reasoning to analyze a humanitarian aid supply chain network with PageRank and Weighted Degree Centrality to optimize resource distribution strategies. |
| [network_flow_planning](v1/network_flow_planning/) | Prescriptive | Plan a multi-tier distribution flow that decides which fulfillment centers to open and how much to ship on every lane to satisfy customer demand at minimum cost. |
| [shipment_compliance](v1/shipment_compliance/) | Rules-based | Define derived business rules for shipment compliance, sourcing risk, and demand escalation. |
| [supplier_reliability](v1/supplier_reliability/) | Prescriptive | Select suppliers to meet product demand while balancing cost and reliability. |
| [supply_chain_resilience](v1/supply_chain_resilience/) | Graph, Rules-based, Prescriptive | A multi-reasoner template that chains blast-radius reachability, graph analysis, rules-based classification, and prescriptive optimization to build a risk-adjusted minimum-cost network flow for supply chain routing. |
| [supply_chain_transport](v1/supply_chain_transport/) | Prescriptive | Minimize inventory holding and transport costs with TL/LTL mode selection. |
| [traveling_salesman](v1/traveling_salesman/) | Prescriptive | Find the shortest route visiting all cities exactly once using the MTZ formulation. |
| [warehouse_allocation](v1/warehouse_allocation/) | Graph, Prescriptive | Allocate inventory across a distribution network using graph centrality, weakly-connected-components, and bridge-route detection to prioritize critical hubs. |

</details>

<details>
<summary>Technology & Telecom (9)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [cell_tower_coverage](v1/cell_tower_coverage/) | Prescriptive | Select candidate cell tower sites and assign demand zones to maximize covered population under budget, tower-count, and capacity limits. |
| [cicd_runner_allocation](v1/cicd_runner_allocation/) | Prescriptive | Assign CI/CD workflow jobs to the cheapest compatible runner type, subject to concurrency limits, with scenario analysis across capacity levels. |
| [datacenter_compute_allocation](v1/datacenter_compute_allocation/) | Predictive, Graph, Rules-based, Prescriptive | Multi-reasoner template (chain follow-up to energy_grid_planning): heterogeneous-graph GNN classification of per-workload utilization probability, hardware-compatibility rules, dependency PageRank, and 24-cell scenario MIP for inside-the-fence GPU allocation across hyperscaler campuses. |
| [memory_supply_allocation](v1/memory_supply_allocation/) | Predictive, Rules-based, Prescriptive, Graph | Monthly rolling-horizon allocation of constrained memory-chip supply across customers with strategic supplier dependencies, named foundries, and raw-material inputs. Four-reasoner chain: predicted supplier capability feeds the optimization, customer-customer paths surface single points of failure, and two what-if scenarios trace supplier-offline and input-shortage cascades. |
| [pod_placement](v1/pod_placement/) | Prescriptive | Assign pods to nodes in a Kubernetes-style cluster subject to per-node CPU / memory / GPU bin-packing, pairwise tenant anti-affinity, deployment co-location affinity, failure-domain spread, gang-placement atomicity, and topology rack-clique rules. Pure CSP via MiniZinc / Chuffed. |
| [sprint_scheduling](v1/sprint_scheduling/) | Prescriptive | Assign backlog issues to developers across sprints, minimizing weighted completion time while respecting capacity and skill constraints. |
| [subscriber_retention](v1/subscriber_retention/) | Graph, Predictive | Telco churn-risk scoring: PageRank over a Subscriber→Subscriber call graph (Graph) plus aggregate-derived call-volume features feed a regression GNN (Predictive) that scores per-subscriber churn risk, then surfaces the highest-risk subscribers per segment for retention campaigns. |
| [telco_network_recovery](v1/telco_network_recovery/) | Predictive, Rules-based, Graph, Prescriptive | Multi-reasoner template: equipment-failure GNN over a heterogeneous graph (with manufacturer advisories), declarative critical-tower rules, call-graph blast radius, and tower-upgrade optimization on a shared telco ontology. |
| [test_data_generation](v1/test_data_generation/) | Prescriptive | Determine optimal row counts for test database tables satisfying schema and referential integrity constraints. |

</details>

<!-- END TEMPLATE INDEX -->

## Choose a template

Use the version folder and template README to pick the example that matches your goal.

- If you want a minimal onboarding example, start with [`v1/simple-start/`](v1/simple-start/).
- If you want to create a new template, start from [`sample-template/`](sample-template/).

For the full list of templates and their descriptions, see the [Templates](#templates) index above.

## Getting started with a template

The exact setup is documented in each template's README, but the workflow is consistent:

1. Pick a template folder.
2. Create a virtual environment inside that folder.
3. Install the template's dependencies.
4. Configure RelationalAI access if the template connects to a live environment.
5. Run the script or notebook described in the template README.

Example workflow:

```bash
cd v1/simple-start
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install .
```

After installation, continue with the template-specific instructions in that folder's README.

## What a template includes

Most templates are designed to be runnable and inspectable without additional repository-level setup.

- **Code**: a small, focused implementation of the use case
- **Sample data**: enough data to exercise the model end to end
- **Documentation**: problem framing, prerequisites, quickstart, and customization notes
- **Metadata**: template metadata used by the [RelationalAI Docs](https://docs.relational.ai/) site to surface the template in the [template gallery](https://docs.relational.ai/build/templates).

## Contributing

To add or update a template:

1. Copy [`sample-template/`](sample-template/) into the version folder you are targeting.
2. Implement the model, runner, sample data, and metadata.
3. Replace the README placeholders with template-specific content.
4. Review the result before opening a pull request.

Repository-level linting for template Python code uses Ruff:

```bash
ruff check path/to/my/template
```

The same check runs in CI via `.github/workflows/lint.yml`.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contribution workflow.
