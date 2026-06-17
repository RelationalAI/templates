# v1 Templates

This directory contains the templates for v1. Each template folder includes its own code, data, and detailed README.

## Template Index

Templates are grouped by industry. Expand an industry to see its templates, the reasoners each uses, and a one-line description.

<details>
<summary>Cross-Industry (4)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [rai-agent-scaffold](./rai-agent-scaffold/) | Graph | Scaffold for packaging a RelationalAI semantic model as a Snowflake Cortex agent and exposing it through Snowflake Intelligence. |
| [shift_assignment](./shift_assignment/) | Prescriptive | Assign workers to shifts based on availability to meet coverage requirements. |
| [simple-start](./simple-start/) | Graph | A minimal notebook to connect to Snowflake, model a small graph, and compute betweenness centrality with RelationalAI. |
| [wildlife-conservation-network](./wildlife-conservation-network/) | Graph | Identify collaboration clusters among wildlife-conservation organizations with Louvain community detection and degree centrality, surfacing key coordination hubs for resource sharing. |

</details>

<details>
<summary>Energy & Utilities (2)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [energy_grid_planning](./energy_grid_planning/) | Graph, Rules-based, Prescriptive | AI data center interconnection planning on the ERCOT (Texas) grid: demand forecasting, grid-vulnerability analysis, compliance rules, and multi-objective optimization. |
| [water_allocation](./water_allocation/) | Prescriptive | Minimize the cost of distributing water from sources to users with nonlinear transmission losses. |

</details>

<details>
<summary>Financial Services (8)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [commercial_underwriting](./commercial_underwriting/) | Rules-based | Eligibility checks and risk-tier classification across a four-level commercial property/casualty hierarchy (insured entity, policy, location, coverage). |
| [entity_resolution](./entity_resolution/) | Graph, Rules-based, Prescriptive | Resolve duplicate policyholder records scattered across an insurer's policy systems and acquired books into one insured party, then total each household's exposure, flag accumulation-limit breaches, and choose the lowest-cost reinsurance cessions to clear them. |
| [financial_index_replication](./financial_index_replication/) | Prescriptive, Rules-based | Select a sparse 20-stock replication basket and weights that track an S&P 500-like benchmark. |
| [fraud-detection](./fraud-detection/) | Graph, Rules-based, Predictive, Prescriptive | Transaction-fraud pipeline: account PageRank and high-volume account flags feed a GNN binary classifier whose per-transaction scores drive a knapsack investigator-budget MILP. |
| [money_laundering_motif_detection](./money_laundering_motif_detection/) | Prescriptive | Detect three classes of layering motif on the same transaction ledger, each demonstrating a different CSP technique that rules / paths / graph reasoning alone cannot enforce: per-vertex aggregate equality (butterfly), pairwise distinctness over a chosen subset (smurf army), and cardinality on a chosen subset (KYC-mix burst). |
| [portfolio_balancing](./portfolio_balancing/) | Prescriptive, Rules-based, Graph | Compliance screening, covariance clustering, and bi-objective Markowitz optimization that traces the risk-return frontier with solver shadow prices, plus a crisis-regime stress test. |
| [synthetic_order_lifecycle](./synthetic_order_lifecycle/) | Prescriptive | Generate synthetic order-lifecycle event traces (PLACE / MODIFY / CANCEL / FILL) that satisfy MiFID II / Reg NMS-flavour sequencing rules. |
| [transaction_screening_local](./transaction_screening_local/) | Rules-based | Triage a transfer ledger with rules-based reasoning on a local DuckDB database, with no Snowflake account required: classify accounts that move money just under reporting thresholds, flag large senders, and expand the investigation to everyone who transacted with a flagged account. |
| [underwriting_audit](./underwriting_audit/) | Prescriptive | Audit an underwriting ruleset against a catalog of properties. For each, either prove it holds (PASS) or return K distinct counterexample applicants that falsify it (FAIL). Multi-property batch audit in multi-solution mode. |

</details>

<details>
<summary>Healthcare & Life Sciences (6)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [diet](./diet/) | Prescriptive | Select foods to satisfy nutritional requirements at minimum cost. |
| [disease-outbreak-prevention](./disease-outbreak-prevention/) | Graph | Rank the highest-risk facilities in a public health network by weighted degree centrality (connection volume and intensity) to prioritize resource deployment during outbreaks. |
| [hospital_staffing](./hospital_staffing/) | Prescriptive | Explore the tradeoff between overtime cost and patient service level using bi-objective optimization with epsilon constraint. |
| [patient_cohort_recruitment](./patient_cohort_recruitment/) | Graph, Rules-based, Prescriptive | Build a clinical-research cohort over a patient knowledge graph: close a kinase-pathway sub-ontology, lift the closure to per-patient eligibility and coverage facts, then pick K patients whose joint coverage spans enough distinct genes, therapies, and adverse events to generalize. |
| [smoker_status_prediction](./smoker_status_prediction/) | Predictive | Predict whether a person is a smoker from demographic and medical attributes plus a network of social connections. |
| [synthetic_eligibility_records](./synthetic_eligibility_records/) | Prescriptive | Generate K distinct, internally consistent member eligibility records per solve in multi-solution mode: each satisfies CMS Medicare-eligibility, age-by-plan-type CFDs, and PCP-network attribution. |

</details>

<details>
<summary>Manufacturing (5)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [bom-reachability](./bom-reachability/) | Graph | Trace transitive dependencies through a bill of materials to identify which raw materials each finished product depends on and which components are structural bottlenecks. |
| [defect_root_cause](./defect_root_cause/) | Graph, Rules-based, Prescriptive | Diagnose a spike in final-test failures on an electronics assembly line by tracing each unit's history back through the bill of materials and the production line, then identifying the smallest set of causes that explains the failures. |
| [factory_production](./factory_production/) | Prescriptive | Maximize production profit under per-factory resource limits, then read the sensitivity marginals (capacity shadow prices and product reduced costs) from one solve. |
| [product_configurator](./product_configurator/) | Prescriptive | Enumerate every feasible build of a configurable product in multi-solution mode: one option per slot subject to feature-model rules, regional regulations, and a price ceiling. |
| [production_planning](./production_planning/) | Prescriptive | Schedule production across machines to meet demand and maximize profit with scenario analysis. |

</details>

<details>
<summary>Retail & Consumer (7)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [ad_spend_allocation](./ad_spend_allocation/) | Prescriptive | Allocate marketing budget across channels and campaigns to maximize conversions. |
| [book_slate_recommendation](./book_slate_recommendation/) | Graph, Prescriptive | Recommend K books per reader and order them by slot, under diversity, freshness, and explainability constraints. |
| [campaign_roi](./campaign_roi/) | Prescriptive | Reallocate marketing campaign budgets across regions to maximize conversions, with per-campaign floor and cap constraints and a regional cap on a paused region. |
| [demand_forecasting](./demand_forecasting/) | Predictive | Forecast next-period unit sales per (store, item, day) with a regression GNN over a heterogeneous retail graph linking sales to stores, items, and item families. |
| [planogram_optimization](./planogram_optimization/) | Predictive, Prescriptive | Decide integer facing counts per SKU to maximize predicted weekly demand under shelf capacity and category cardinality limits, where per-(SKU, facing_count) demand comes from a regression model. |
| [retail_markdown](./retail_markdown/) | Prescriptive | Set discount levels across weeks to maximize revenue while clearing inventory. |
| [retail_planning](./retail_planning/) | Predictive, Prescriptive | Predict article sales and customer churn with GNNs, then optimize markdown pricing and inventory planning to maximize revenue and minimize costs. |

</details>

<details>
<summary>Supply Chain & Logistics (9)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [demand_planning_temporal](./demand_planning_temporal/) | Prescriptive | Plan weekly production and inventory across sites over a date-filtered planning horizon to minimize total cost while meeting demand. |
| [humanitarian-aid-supply-chain](./humanitarian-aid-supply-chain/) | Graph | Analyze a humanitarian aid supply-chain network with PageRank and weighted degree centrality to optimize resource distribution. |
| [network_flow_planning](./network_flow_planning/) | Prescriptive | Plan a multi-tier distribution flow that decides which fulfillment centers to open and how much to ship on every lane to satisfy customer demand at minimum cost. |
| [shipment_compliance](./shipment_compliance/) | Rules-based | Derived classifications for shipment compliance, sourcing risk, and demand escalation. |
| [supplier_reliability](./supplier_reliability/) | Prescriptive | Select suppliers to meet product demand at minimum cost, with sensitivity marginals and supplier-disruption scenario analysis. |
| [supply_chain_resilience](./supply_chain_resilience/) | Graph, Rules-based, Prescriptive | Chain blast-radius reachability, network analysis, and rule-based risk classification into a risk-adjusted minimum-cost network flow for supply-chain routing. |
| [supply_chain_transport](./supply_chain_transport/) | Prescriptive | Minimize inventory holding and transport costs with TL/LTL mode selection. |
| [traveling_salesman](./traveling_salesman/) | Prescriptive | Find the shortest route visiting all cities exactly once using the MTZ formulation. |
| [warehouse_allocation](./warehouse_allocation/) | Graph, Prescriptive | Allocate inventory across a distribution network using centrality, weakly-connected components, and bridge-route detection to prioritize critical hubs. |

</details>

<details>
<summary>Technology & Telecom (9)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [cell_tower_coverage](./cell_tower_coverage/) | Prescriptive | Select candidate cell tower sites and assign demand zones to maximize covered population under budget, tower-count, and capacity limits. |
| [cicd_runner_allocation](./cicd_runner_allocation/) | Prescriptive | Assign CI/CD workflow jobs to the cheapest compatible runner type, subject to concurrency limits, with scenario analysis across capacity levels and conflict analysis to diagnose an infeasible outage. |
| [datacenter_compute_allocation](./datacenter_compute_allocation/) | Predictive, Graph, Rules-based, Prescriptive | Inside-the-fence GPU allocation across hyperscaler campuses, a chain follow-up to energy_grid_planning: GNN-predicted per-workload utilization, hardware-compatibility rules, dependency PageRank, and a 24-cell scenario MIP. |
| [memory_supply_allocation](./memory_supply_allocation/) | Predictive, Rules-based, Prescriptive, Graph | Monthly rolling-horizon allocation of constrained memory-chip supply across customers with supplier dependencies, named foundries, and raw-material inputs: predicted supplier capability feeds the optimization, customer-customer paths surface single points of failure, and two what-if scenarios trace supplier-offline and input-shortage cascades. |
| [pod_placement](./pod_placement/) | Prescriptive | Assign pods to nodes in a Kubernetes-style cluster subject to per-node CPU / memory / GPU bin-packing, pairwise tenant anti-affinity, deployment co-location affinity, failure-domain spread, gang-placement atomicity, and topology rack-clique rules. Pure CSP via MiniZinc / Chuffed. |
| [sprint_scheduling](./sprint_scheduling/) | Prescriptive | Assign backlog issues to developers across sprints, minimizing weighted completion time while respecting capacity and skill constraints. |
| [subscriber_retention](./subscriber_retention/) | Graph, Predictive | Telco churn-risk scoring: PageRank over a Subscriber→Subscriber call graph plus aggregate-derived call-volume features feed a regression GNN that scores per-subscriber churn risk, then surfaces the highest-risk subscribers per segment. |
| [telco_network_recovery](./telco_network_recovery/) | Predictive, Rules-based, Graph, Prescriptive | Tower-upgrade planning on a shared telco ontology: an equipment-failure GNN over a heterogeneous graph (with manufacturer advisories), declarative critical-tower rules, and customer-impact analysis (revenue × churn, with PageRank). |
| [test_data_generation](./test_data_generation/) | Prescriptive | Determine optimal row counts for test database tables satisfying schema and referential integrity constraints. |

</details>
