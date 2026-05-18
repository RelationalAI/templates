# v1 Templates

This directory contains the templates for v1. Each template folder includes its own code, data, and detailed README.

## Template Index

| Template | Description |
| --- | --- |
| [ad_spend_allocation](./ad_spend_allocation/) | Allocate marketing budget across channels and campaigns to maximize conversions. |
| [bom-reachability](./bom-reachability/) | Trace transitive dependencies through a bill of materials to identify which raw materials each finished product depends on and which components are structural bottlenecks. |
| [campaign_roi](./campaign_roi/) | Reallocate marketing campaign budgets across regions to maximize conversions, with per-campaign floor and cap constraints and a regional cap on a paused region. |
| [cicd_runner_allocation](./cicd_runner_allocation/) | Assign CI/CD workflow jobs to the cheapest compatible runner type, subject to concurrency limits, with scenario analysis across capacity levels. |
| [commercial_underwriting](./commercial_underwriting/) | Run rules-based eligibility checks and risk-tier classification across a four-level commercial property/casualty hierarchy (insured entity, policy, location, coverage). |
| [datacenter_compute_allocation](./datacenter_compute_allocation/) | Multi-reasoner template (chain follow-up to energy_grid_planning): heterogeneous-graph GNN classification of per-workload utilization probability, hardware-compatibility rules, dependency PageRank, and 24-cell scenario MIP for inside-the-fence GPU allocation across hyperscaler campuses. |
| [demand_forecasting](./demand_forecasting/) | Forecast next-period unit sales per (store, item, day) with a regression GNN over a heterogeneous retail knowledge graph: sales transactions linked to stores, items, and item families so the GNN propagates signal through the store and product hierarchies. |
| [demand_planning_temporal](./demand_planning_temporal/) | Plan weekly production and inventory across sites over a date-filtered planning horizon to minimize total cost while meeting demand. |
| [diet](./diet/) | Select foods to satisfy nutritional requirements at minimum cost. |
| [disease-outbreak-prevention](./disease-outbreak-prevention/) | Use weighted degree centrality to identify the highest-risk healthcare facilities in a public health network, considering both connection volume and intensity, to prioritize resource deployment during disease outbreaks. |
| [energy_grid_planning](./energy_grid_planning/) | Multi-reasoner template: demand forecasting, grid vulnerability analysis, compliance rules, and multi-objective optimization for AI data center interconnection planning on the ERCOT (Texas) grid. |
| [factory_production](./factory_production/) | Maximize profit from production with limited resource availability per factory. |
| [financial_index_replication](./financial_index_replication/) | Prescriptive optimization template for selecting a sparse 20-stock replication basket and weights that track an S&P 500-like benchmark. |
| [fraud-detection](./fraud-detection/) | Multi-reasoner transaction-fraud pipeline: account PageRank (Graph) + high-volume account flags (Rules) feed a GNN binary classifier (Predictive) whose per-transaction scores drive a knapsack investigator-budget MILP (Prescriptive). |
| [hospital_staffing](./hospital_staffing/) | Explore the tradeoff between overtime cost and patient service level using bi-objective optimization with epsilon constraint. |
| [humanitarian-aid-supply-chain](./humanitarian-aid-supply-chain/) | Use graph reasoning to analyze a humanitarian aid supply chain network with PageRank and Weighted Degree Centrality to optimize resource distribution strategies. |
| [machine_maintenance](./machine_maintenance/) | A multi-reasoner template that chains querying, graph analysis, rules-based classification, and prescriptive optimization to schedule preventive maintenance, surface hidden operational risk, and recommend cross-training to eliminate concentration vulnerabilities. |
| [network_flow_planning](./network_flow_planning/) | Plan a multi-tier distribution flow that decides which fulfillment centers to open and how much to ship on every lane to satisfy customer demand at minimum cost. |
| [portfolio_balancing](./portfolio_balancing/) | Multi-reasoner template: rules-based compliance, covariance clustering, and bi-objective Markowitz optimization with a crisis-regime stress test. |
| [product_configurator](./product_configurator/) | Enumerate every feasible build of a configurable product using a CSP solver in multi-solution mode: one option per slot subject to feature-model rules, regional regulations, and a price ceiling. |
| [production_planning](./production_planning/) | Schedule production across machines to meet demand and maximize profit with scenario analysis. |
| [rai-agent-scaffold](./rai-agent-scaffold/) | Scaffold for packaging a RelationalAI semantic model as a Snowflake Cortex agent and exposing it through Snowflake Intelligence. |
| [retail_markdown](./retail_markdown/) | Set discount levels across weeks to maximize revenue while clearing inventory. |
| [retail_planning](./retail_planning/) | Predict article sales and customer churn with GNNs, then optimize markdown pricing and inventory planning to maximize revenue and minimize costs. |
| [shift_assignment](./shift_assignment/) | Assign workers to shifts based on availability to meet coverage requirements. |
| [shipment_compliance](./shipment_compliance/) | Define derived business rules for shipment compliance, sourcing risk, and demand escalation. |
| [simple-start](./simple-start/) | A minimal notebook to connect to Snowflake, model a small graph, and compute betweenness centrality with RelationalAI. |
| [sprint_scheduling](./sprint_scheduling/) | Assign backlog issues to developers across sprints, minimizing weighted completion time while respecting capacity and skill constraints. |
| [subscriber_retention](./subscriber_retention/) | Telco churn-risk scoring: PageRank over a Subscriber→Subscriber call graph (Graph) plus aggregate-derived call-volume features feed a regression GNN (Predictive) that scores per-subscriber churn risk, then surfaces the highest-risk subscribers per segment for retention campaigns. |
| [supplier_reliability](./supplier_reliability/) | Select suppliers to meet product demand while balancing cost and reliability. |
| [supply_chain_resilience](./supply_chain_resilience/) | A multi-reasoner template that chains blast-radius reachability, graph analysis, rules-based classification, and prescriptive optimization to build a risk-adjusted minimum-cost network flow for supply chain routing. |
| [supply_chain_transport](./supply_chain_transport/) | Minimize inventory holding and transport costs with TL/LTL mode selection. |
| [synthetic_eligibility_records](./synthetic_eligibility_records/) | Generate K distinct, internally consistent member eligibility records per solve using a CSP solver in multi-solution mode: each record satisfies CMS Medicare-eligibility, age-by-plan-type CFDs, and PCP-network attribution. |
| [synthetic_order_lifecycle](./synthetic_order_lifecycle/) | Generate synthetic order-lifecycle event traces (PLACE / MODIFY / CANCEL / FILL) that satisfy MiFID II / Reg NMS-flavour sequencing rules using a CSP solver. |
| [telco_network_recovery](./telco_network_recovery/) | Multi-reasoner template: GNN demand forecasting, declarative critical-tower rules, call-graph blast radius, and tower-upgrade optimization on a shared telco ontology. |
| [test_data_generation](./test_data_generation/) | Determine optimal row counts for test database tables satisfying schema and referential integrity constraints. |
| [traveling_salesman](./traveling_salesman/) | Find the shortest route visiting all cities exactly once using the MTZ formulation. |
| [warehouse_allocation](./warehouse_allocation/) | Allocate inventory across a distribution network using graph centrality, weakly-connected-components, and bridge-route detection to prioritize critical hubs. |
| [water_allocation](./water_allocation/) | Minimize the cost of distributing water from sources to users with nonlinear transmission losses. |
| [wildlife-conservation-network](./wildlife-conservation-network/) | Use the Louvain community detection algorithm and degree centrality analysis to identify collaboration clusters among wildlife conservation organizations, helping optimize resource sharing and identify key coordination hubs. |
