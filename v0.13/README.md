# v0.13 Templates

This directory contains the templates for v0.13. Each template folder includes its own code, data, and detailed README.

## Template Index

Templates are grouped by industry. Expand an industry to see its templates, the reasoners each uses, and a one-line description.

<details>
<summary>Cross-Industry (1)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [shift_assignment](./shift_assignment/) | Prescriptive | Assign workers to shifts based on availability while meeting minimum coverage and per-worker capacity constraints. |

</details>

<details>
<summary>Energy & Utilities (2)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [grid_interconnection](./grid_interconnection/) | Prescriptive | Approve data center interconnection requests and substation upgrades to maximize net revenue within capital budget. |
| [water_allocation](./water_allocation/) | Prescriptive | Allocate water from sources to users at minimum cost while meeting demand, subject to connection limits and transmission losses. |

</details>

<details>
<summary>Financial Services (1)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [portfolio_balancing](./portfolio_balancing/) | Prescriptive | Allocate investment across stocks to minimize risk while achieving a target return. |

</details>

<details>
<summary>Healthcare & Life Sciences (2)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [diet](./diet/) | Prescriptive | Select foods to satisfy daily nutritional requirements at minimum cost. |
| [hospital_staffing](./hospital_staffing/) | Prescriptive | Assign nurses to shifts to minimize overtime cost and overflow penalties from unmet patient demand. |

</details>

<details>
<summary>Manufacturing (3)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [factory_production](./factory_production/) | Prescriptive | Choose production quantities per machine-product pair to maximize profit while meeting minimum production requirements. |
| [machine_maintenance](./machine_maintenance/) | Prescriptive | Schedule preventive maintenance across time slots to minimize cost while respecting crew-hour capacity and machine conflicts. |
| [production_planning](./production_planning/) | Prescriptive | Schedule production across machines to meet demand while maximizing profit. |

</details>

<details>
<summary>Retail & Consumer (2)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [ad_spend_allocation](./ad_spend_allocation/) | Prescriptive | Allocate a fixed budget across channel–campaign combinations to maximize expected conversions, subject to channel spend bounds and per-campaign budget limits. |
| [retail_markdown](./retail_markdown/) | Prescriptive | Set discount levels for products across a selling season to maximize revenue while clearing inventory. |

</details>

<details>
<summary>Supply Chain & Logistics (7)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [inventory_rebalancing](./inventory_rebalancing/) | Prescriptive | Transfer inventory between warehouse sites to meet demand at minimum cost. |
| [network_flow](./network_flow/) | Prescriptive | Maximize flow through a capacitated network from a source node. |
| [order_fulfillment](./order_fulfillment/) | Prescriptive | Assign customer orders to fulfillment centers to minimize shipping and fixed costs. |
| [supplier_reliability](./supplier_reliability/) | Prescriptive | Select suppliers to meet product demand while balancing cost and reliability. |
| [supply_chain_transport](./supply_chain_transport/) | Prescriptive | Route shipments from warehouses to customers using multiple transport modes to minimize cost. |
| [traveling_salesman](./traveling_salesman/) | Prescriptive | Find the shortest route visiting all cities exactly once and returning to the start. |
| [vehicle_scheduling](./vehicle_scheduling/) | Prescriptive | Assign trips to vehicles to minimize total cost, including fixed vehicle activation costs and per-mile costs. |

</details>

<details>
<summary>Technology & Telecom (1)</summary>

| Template | Reasoners | Description |
| --- | --- | --- |
| [test_data_generation](./test_data_generation/) | Prescriptive | Determine feasible row counts for test database tables that satisfy schema constraints, then generate example synthetic rows. |

</details>
