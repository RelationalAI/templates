# RelationalAI Templates

This repository contains runnable RelationalAI templates that demonstrate end-to-end solution pattern examples across optimization and constraint satisfaction, graph analytics and path-finding, rules-based reasoning, and graph neural network predictions. 

## Templates

Each template lives in its own folder in the `v1` directory. Within a folder, you will usually find:

- `README.md` with the problem statement, prerequisites, and run instructions
- `pyproject.toml` for template-local dependencies
- a main runner such as `<template>.py` or a notebook
- `data/` containing sample input data when the template uses local files
- `runbook.md` with ordered prompts to recreate or adapt the template using a coding agent with RelationalAI skills (multi-reasoner templates)

The index below covers the current templates. Expand an industry to see its templates with reasoners and a description.

<!-- BEGIN TEMPLATE INDEX -->

<details>
<summary>Cross-Industry (4)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [rai-agent-scaffold](v1/rai-agent-scaffold/) | Graph | Scaffold for packaging a RelationalAI semantic model as a Snowflake Cortex agent and exposing it through Snowflake Intelligence. |
| [shift_assignment](v1/shift_assignment/) | Prescriptive | Assign workers to shifts based on availability to meet coverage requirements. |
| [simple-start](v1/simple-start/) | Graph | A minimal notebook to connect to Snowflake, model a small graph, and compute betweenness centrality with RelationalAI. |
| [wildlife-conservation-network](v1/wildlife-conservation-network/) | Graph | Identify collaboration clusters among wildlife-conservation organizations with Louvain community detection and degree centrality, surfacing key coordination hubs for resource sharing. |

</details>

<details>
<summary>Energy & Utilities (2)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [energy_grid_planning](v1/energy_grid_planning/) | Graph, Rules-based, Prescriptive | Plan how to connect AI data centers to the Electric Reliability Council of Texas (ERCOT) power grid. Forecasts demand, finds vulnerable parts of the grid, applies compliance rules, and balances competing objectives to recommend where to interconnect. |
| [water_allocation](v1/water_allocation/) | Prescriptive | Minimize the cost of distributing water from sources to users with nonlinear transmission losses. |

</details>

<details>
<summary>Financial Services (9)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [commercial_underwriting](v1/commercial_underwriting/) | Rules-based | Eligibility checks and risk-tier classification across a four-level commercial property/casualty hierarchy (insured entity, policy, location, coverage). |
| [entity_resolution](v1/entity_resolution/) | Graph, Rules-based, Prescriptive | Resolve duplicate policyholder records across an insurer's policy systems and acquired books into one insured party. Total each household's exposure, flag accumulation-limit breaches, and choose the lowest-cost reinsurance cessions to clear them. |
| [financial_index_replication](v1/financial_index_replication/) | Prescriptive, Rules-based | Select a sparse 20-stock replication basket and weights that track an S&P 500-like benchmark. |
| [fraud-detection](v1/fraud-detection/) | Graph, Rules-based, Predictive, Prescriptive | Transaction-fraud pipeline where account PageRank and high-volume account flags feed a graph neural network (GNN) binary classifier whose per-transaction scores drive a knapsack investigator-budget mixed-integer linear program (MILP). |
| [money_laundering_motif_detection](v1/money_laundering_motif_detection/) | Prescriptive | Detect three classes of money-laundering layering motif on one transaction ledger using constraint-satisfaction (CSP) reasoning. Each motif enforces a joint condition across a solver-chosen subset of accounts and edges. |
| [portfolio_balancing](v1/portfolio_balancing/) | Prescriptive, Rules-based, Graph | Compliance screening, covariance clustering, and bi-objective Markowitz optimization that traces the risk-return frontier with solver shadow prices, plus a crisis-regime stress test. |
| [synthetic_order_lifecycle](v1/synthetic_order_lifecycle/) | Prescriptive | Generate synthetic order-lifecycle event traces (PLACE / MODIFY / CANCEL / FILL) that satisfy MiFID II / Reg NMS-flavour sequencing rules. |
| [transaction_screening_local](v1/transaction_screening_local/) | Rules-based | Triage a transfer ledger with rules-based reasoning on a local DuckDB database, with no Snowflake account required: classify accounts that move money just under reporting thresholds, flag large senders, and expand the investigation to everyone who transacted with a flagged account. |
| [underwriting_audit](v1/underwriting_audit/) | Prescriptive | Audit an underwriting ruleset against a catalog of required properties. For each property, the solver either proves it always holds or returns concrete counterexample applicants that break it. |

</details>

<details>
<summary>Healthcare & Life Sciences (6)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [diet](v1/diet/) | Prescriptive | Select foods to satisfy nutritional requirements at minimum cost. |
| [disease-outbreak-prevention](v1/disease-outbreak-prevention/) | Graph | Rank the highest-risk facilities in a public health network by weighted degree centrality (connection volume and intensity) to prioritize resource deployment during outbreaks. |
| [hospital_staffing](v1/hospital_staffing/) | Prescriptive | Explore the tradeoff between overtime cost and patient service level using bi-objective optimization with epsilon constraint. |
| [patient_cohort_recruitment](v1/patient_cohort_recruitment/) | Graph, Rules-based, Prescriptive | Build a clinical-research cohort over a patient knowledge graph. It selects a small set of eligible patients that together span enough distinct genes, therapies, and adverse events for a study to generalize. |
| [smoker_status_prediction](v1/smoker_status_prediction/) | Predictive | Predict whether a person is a smoker from demographic and medical attributes plus a network of social connections. |
| [synthetic_eligibility_records](v1/synthetic_eligibility_records/) | Prescriptive | Generate K distinct, internally consistent member eligibility records per solve in multi-solution mode: each satisfies CMS Medicare-eligibility, age-by-plan-type CFDs, and PCP-network attribution. |

</details>

<details>
<summary>Manufacturing (5)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [bom-reachability](v1/bom-reachability/) | Graph | Trace transitive dependencies through a bill of materials to identify which raw materials each finished product depends on and which components are structural bottlenecks. |
| [defect_root_cause](v1/defect_root_cause/) | Graph, Rules-based, Prescriptive | Diagnose a spike in final-test failures on an electronics assembly line by tracing each unit's history back through the bill of materials and the production line, then identifying the smallest set of causes that explains the failures. |
| [factory_production](v1/factory_production/) | Prescriptive | Maximize production profit under per-factory resource limits, then read the sensitivity marginals (capacity shadow prices and product reduced costs) from one solve. |
| [product_configurator](v1/product_configurator/) | Prescriptive | Enumerate every feasible build of a configurable product with a constraint solver in multi-solution mode. Each build picks one option per slot subject to feature-model rules, regional regulations, and a price ceiling. |
| [production_planning](v1/production_planning/) | Prescriptive | Schedule production across machines to meet demand and maximize profit with scenario analysis. |

</details>

<details>
<summary>Retail & Consumer (7)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [ad_spend_allocation](v1/ad_spend_allocation/) | Prescriptive | Allocate a marketing budget across advertising channels and campaigns to maximize expected conversions. Sweeps three budget levels in a single solve to show where extra budget stops paying off. |
| [book_slate_recommendation](v1/book_slate_recommendation/) | Graph, Prescriptive | Recommend a ranked slate of books for each reader that balances relevance, diversity, and freshness. Produces an ordered, explainable set of picks per reader. |
| [campaign_roi](v1/campaign_roi/) | Prescriptive | Reallocate marketing campaign budgets across regions to maximize conversions, with per-campaign floor and cap constraints and a regional cap on a paused region. |
| [demand_forecasting](v1/demand_forecasting/) | Predictive | Forecast next-period unit sales per store, item, and day with a regression graph neural network (GNN) over a heterogeneous retail graph linking sales to stores, items, and item families. |
| [planogram_optimization](v1/planogram_optimization/) | Predictive, Prescriptive | Decide integer facing counts per SKU to maximize predicted weekly demand under shelf capacity and category cardinality limits, where per-(SKU, facing_count) demand comes from a regression model. |
| [retail_markdown](v1/retail_markdown/) | Prescriptive | Set discount levels across weeks to maximize revenue while clearing inventory. |
| [retail_planning](v1/retail_planning/) | Predictive, Prescriptive | Predict article sales and customer churn with graph neural networks (GNNs), then optimize markdown pricing and inventory planning to maximize revenue and minimize costs. |

</details>

<details>
<summary>Supply Chain & Logistics (9)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [demand_planning_temporal](v1/demand_planning_temporal/) | Prescriptive | Plan weekly production and inventory across sites over a date-filtered planning horizon to minimize total cost while meeting demand. |
| [humanitarian-aid-supply-chain](v1/humanitarian-aid-supply-chain/) | Graph | Analyze a humanitarian aid supply-chain network with PageRank and weighted degree centrality to optimize resource distribution. |
| [network_flow_planning](v1/network_flow_planning/) | Prescriptive | Plan a multi-tier distribution flow that decides which fulfillment centers to open and how much to ship on every lane to satisfy customer demand at minimum cost. |
| [shipment_compliance](v1/shipment_compliance/) | Rules-based | Derived classifications for shipment compliance, sourcing risk, and demand escalation. |
| [supplier_reliability](v1/supplier_reliability/) | Prescriptive | Select suppliers to meet product demand at minimum cost, with sensitivity marginals and supplier-disruption scenario analysis. |
| [supply_chain_resilience](v1/supply_chain_resilience/) | Graph, Rules-based, Prescriptive | Chain blast-radius reachability, network analysis, and rule-based risk classification into a risk-adjusted minimum-cost network flow for supply-chain routing. |
| [supply_chain_transport](v1/supply_chain_transport/) | Prescriptive | Minimize inventory holding and transport costs with TL/LTL mode selection. |
| [traveling_salesman](v1/traveling_salesman/) | Prescriptive | Find the shortest route that visits every city exactly once and returns home. A self-contained starting point for building route optimization on RelationalAI. |
| [warehouse_allocation](v1/warehouse_allocation/) | Graph, Prescriptive | Allocate inventory across a distribution network using centrality, weakly-connected components, and bridge-route detection to prioritize critical hubs. |

</details>

<details>
<summary>Technology & Telecom (11)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [cell_tower_coverage](v1/cell_tower_coverage/) | Prescriptive | Choose which candidate cell tower sites to build and assign demand zones to them, maximizing covered population under budget, tower-count, and capacity limits. |
| [cicd_runner_allocation](v1/cicd_runner_allocation/) | Prescriptive | Assign continuous-integration and continuous-delivery (CI/CD) workflow jobs to the cheapest compatible runner within concurrency limits. Sweep capacity scenarios and diagnose an infeasible maintenance outage with conflict analysis. |
| [cybersecurity-attack-paths](v1/cybersecurity-attack-paths/) | Graph | Trace multi-step cyber attack chains across an enterprise asset graph by composing attacker techniques in order, then rank the routes that reach crown-jewel systems by their total exposure. |
| [datacenter_compute_allocation](v1/datacenter_compute_allocation/) | Predictive, Graph, Rules-based, Prescriptive | Allocate GPU capacity across hyperscaler campuses using a graph neural network (GNN) that predicts per-workload utilization, hardware-compatibility rules, dependency PageRank, and a 24-cell scenario mixed-integer program (MIP). Picks up where energy_grid_planning leaves off. |
| [it-dependency-mapping](v1/it-dependency-mapping/) | Graph | Map the downstream dependency structure of a software and data-pipeline estate by enumerating variable-length paths over an acyclic dependency graph. Surface the longest end-to-end chains and the owners along them to see a change or outage's full blast radius. |
| [memory_supply_allocation](v1/memory_supply_allocation/) | Predictive, Rules-based, Prescriptive, Graph | Allocate limited memory-chip supply across customers month by month to maximize margin while protecting key accounts. Also surfaces which suppliers and raw materials put the plan most at risk. |
| [pod_placement](v1/pod_placement/) | Prescriptive | Assign pods to nodes in a Kubernetes-style cluster subject to per-node CPU, memory, and GPU bin-packing, pairwise tenant anti-affinity, deployment co-location affinity, failure-domain spread, gang-placement atomicity, and topology rack-clique rules, solved as a pure constraint satisfaction problem (CSP). |
| [sprint_scheduling](v1/sprint_scheduling/) | Prescriptive | Assign backlog issues to developers across sprints, minimizing weighted completion time while respecting capacity and skill constraints. Uses mixed-integer programming (MIP). |
| [subscriber_retention](v1/subscriber_retention/) | Graph, Predictive | Score every telco subscriber for churn risk using a graph neural network (GNN) that learns from both plan attributes and each subscriber's position in the call network, then surface the highest-risk subscribers per segment for retention campaigns. |
| [telco_network_recovery](v1/telco_network_recovery/) | Predictive, Rules-based, Graph, Prescriptive | Tower-upgrade planning on a shared telco ontology: an equipment-failure graph neural network (GNN) over a heterogeneous graph (with manufacturer advisories), declarative critical-tower rules, and customer-impact analysis (revenue times churn, with PageRank). |
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
