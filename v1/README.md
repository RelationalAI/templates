# v1 Templates

This directory contains the templates for v1. Each template folder includes its own code, data, and detailed README.

## Template Index

| Template | Description |
| --- | --- |
| [ad_spend_allocation](./ad_spend_allocation/) | Allocate marketing budget across channels and campaigns to maximize conversions. |
| [bom-reachability](./bom-reachability/) | Trace transitive dependencies through a bill of materials to identify which raw materials each finished product depends on and which components are structural bottlenecks. |
| [cicd_runner_allocation](./cicd_runner_allocation/) | Assign CI/CD workflow jobs to the cheapest compatible runner type, subject to concurrency limits, with scenario analysis across capacity levels. |
| [demand_planning_temporal](./demand_planning_temporal/) | Plan weekly production and inventory across sites over a date-filtered planning horizon to minimize total cost while meeting demand. |
| [diet](./diet/) | Select foods to satisfy nutritional requirements at minimum cost. |
| [disease-outbreak-prevention](./disease-outbreak-prevention/) | Use weighted degree centrality to identify the highest-risk healthcare facilities in a public health network, considering both connection volume and intensity, to prioritize resource deployment during disease outbreaks. |
| [energy_grid_planning](./energy_grid_planning/) | Multi-reasoner template: demand forecasting, grid vulnerability analysis, compliance rules, and multi-objective optimization for AI data center interconnection planning on the ERCOT (Texas) grid. |
| [factory_production](./factory_production/) | Maximize profit from production with limited resource availability per factory. |
| [fraud-detection](./fraud-detection/) | Use graph reasoning to find suspicious users based on shared identifiers and uncommon sharing patterns. |
| [hospital_staffing](./hospital_staffing/) | Explore the tradeoff between overtime cost and patient service level using bi-objective optimization with epsilon constraint. |
| [humanitarian-aid-supply-chain](./humanitarian-aid-supply-chain/) | Use graph reasoning to analyze a humanitarian aid supply chain network with PageRank and Weighted Degree Centrality to optimize resource distribution strategies. |
| [inventory_rebalancing](./inventory_rebalancing/) | Transfer inventory through a warehouse-hub-store network to meet demand at minimum shipping cost, with flow conservation at transit nodes. |
| [machine_maintenance](./machine_maintenance/) | A multi-reasoner template that chains querying, graph analysis, rules-based classification, and prescriptive optimization to schedule preventive maintenance, surface hidden operational risk, and recommend cross-training to eliminate concentration vulnerabilities. |
| [order_fulfillment](./order_fulfillment/) | Assign customer orders to fulfillment centers to minimize total shipping and fixed operating costs. |
| [portfolio_balancing](./portfolio_balancing/) | Multi-reasoner template: rules-based compliance analysis chained with bi-objective Markowitz optimization. |
| [production_planning](./production_planning/) | Schedule production across machines to meet demand and maximize profit with scenario analysis. |
| [rai-agent-scaffold](./rai-agent-scaffold/) | Scaffold for packaging a RelationalAI semantic model as a Snowflake Cortex agent and exposing it through Snowflake Intelligence. |
| [retail_markdown](./retail_markdown/) | Set discount levels across weeks to maximize revenue while clearing inventory. |
| [retail_planning](./retail_planning/) | Predict article sales and customer churn with GNNs, then optimize markdown pricing and inventory planning to maximize revenue and minimize costs. |
| [shift_assignment](./shift_assignment/) | Assign workers to shifts based on availability to meet coverage requirements. |
| [shipment_compliance](./shipment_compliance/) | Define derived business rules for shipment compliance, sourcing risk, and demand escalation. |
| [simple-start](./simple-start/) | A minimal notebook to connect to Snowflake, model a small graph, and compute betweenness centrality with RelationalAI. |
| [site-centrality-network](./site-centrality-network/) | Identify the most critical sites in a supply chain network using weakly connected components, bridge detection, and eigenvector centrality to assess resilience and detect single points of failure. |
| [sprint_scheduling](./sprint_scheduling/) | Assign backlog issues to developers across sprints, minimizing weighted completion time while respecting capacity and skill constraints. |
| [supplier-impact-analysis](./supplier-impact-analysis/) | Trace multi-hop supply chain dependencies to identify which suppliers high-value customers depend on and assess the blast radius of a supplier disruption, including affected customers and products at risk. |
| [supplier_reliability](./supplier_reliability/) | Select suppliers to meet product demand while balancing cost and reliability. |
| [supply_chain_resilience](./supply_chain_resilience/) | A multi-reasoner template that chains graph analysis, rules-based classification, and prescriptive optimization to build a risk-adjusted minimum-cost network flow for supply chain routing. |
| [supply_chain_transport](./supply_chain_transport/) | Minimize inventory holding and transport costs with TL/LTL mode selection. |
| [test_data_generation](./test_data_generation/) | Determine optimal row counts for test database tables satisfying schema and referential integrity constraints. |
| [traveling_salesman](./traveling_salesman/) | Find the shortest route visiting all cities exactly once using the MTZ formulation. |
| [warehouse_allocation](./warehouse_allocation/) | Allocate inventory across a distribution network using graph centrality to prioritize critical hubs. |
| [water_allocation](./water_allocation/) | Minimize the cost of distributing water from sources to users with nonlinear transmission losses. |
| [wildlife-conservation-network](./wildlife-conservation-network/) | Use the Louvain community detection algorithm and degree centrality analysis to identify collaboration clusters among wildlife conservation organizations, helping optimize resource sharing and identify key coordination hubs. |
