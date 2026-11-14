---
title: "Supply Chain Transport"
description: "Minimize inventory holding and transport costs with TL/LTL mode selection."
featured: false
experience_level: intermediate
industry: "Supply Chain & Logistics"
reasoning_types:
  - Prescriptive
tags:
  - supply-chain
  - transportation
  - mixed-integer-programming
  - logistics
---

## What this template is for

In freight logistics, choosing between truckload (TL) and less-than-truckload (LTL) shipping modes involves a cost trade-off. TL shipments have a fixed cost per truck but offer lower per-unit rates for large volumes. LTL shipments have a piecewise cost structure that is cheaper for small volumes but expensive at scale. On top of mode selection, freight sitting in a vendor warehouse incurs inventory holding costs. The optimal strategy balances when to ship, how much to ship, and which mode to use.

This template formulates a mixed-integer program that jointly optimizes inventory holding, transport mode selection (TL vs LTL), and shipment timing for multiple freight groups. Each freight group has its own inventory window, transport window, and arrival deadline. The solver determines the cost-minimizing plan that ships all freight on time while respecting TL capacity limits and LTL piecewise cost breakpoints.

The model demonstrates several advanced techniques: multi-period inventory flow conservation, binary mode selection with big-M coupling, piecewise linear cost modeling for LTL segments, and arrival-day linking through transit times.

## Who this is for

- Supply chain planners optimizing freight consolidation and mode selection.
- Logistics analysts comparing TL vs LTL cost trade-offs.
- Operations researchers building multi-period transport models.
- Developers learning mixed-integer programming with RelationalAI.
- **Assumed knowledge**: comfortable reading Python; the transport and optimization terms are explained as they come up. No prior RelationalAI experience is required to run it.

## What you'll build

- A cost-minimizing transport plan -- per-freight-group inventory levels, shipment quantities, mode choice, and arrival days -- produced by the **prescriptive** reasoner as a mixed-integer program.
- A binary mode-selection decision (truckload vs less-than-truckload) coupled to shipment volume through big-M constraints, expressed as **prescriptive** decision variables and constraints.
- A piecewise-linear cost model for less-than-truckload freight, with per-segment breakpoint variables the solver activates as volume grows.
- Arrival days derived from departure day and transit time, linked into the solve so on-time-arrival deadlines are enforced as constraints.

## What's included

- `model/__init__.py` -- ontology, formulation, and solver configuration; `rai models deploy --path model` deploys it to your Snowflake account, where each refresh runs the solve
- `queries/transport_plan.py` -- prints the report from the deployed model: the solve status and cost and the inventory, transport, and arrival tables
- `runbook.md` -- a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself
- `data/freight_groups.csv` -- 2 freight groups with inventory/transport/arrival windows
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (Quickstart step 4 below covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai` == 2.1.1)

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.SUPPLY_CHAIN_TRANSPORT_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.SUPPLY_CHAIN_TRANSPORT_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.SUPPLY_CHAIN_TRANSPORT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.SUPPLY_CHAIN_TRANSPORT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.SUPPLY_CHAIN_TRANSPORT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.SUPPLY_CHAIN_TRANSPORT_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.SUPPLY_CHAIN_TRANSPORT_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.SUPPLY_CHAIN_TRANSPORT_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/supply_chain_transport.zip), unzip it, and enter the template directory:

   ```bash
   unzip supply_chain_transport.zip
   cd supply_chain_transport
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: supply_chain_transport_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.SUPPLY_CHAIN_TRANSPORT               # published views and tables
     identity:
       internal_schema: <DB>.SUPPLY_CHAIN_TRANSPORT_META      # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the model's first refresh, which runs the solve. Each refresh of the deployed model runs the solve again.

   Deploying again without changing the model applies no updates and does not solve again. A change to the model or to `problem.configure(...)` redeploys, and the redeploy's refresh solves.

6. **Query the results**

   Print the report from the deployed model:

   ```bash
   python -m queries.transport_plan
   ```

   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 1444.0

   Status: OPTIMAL
   Total cost: $1444.00

   === Transport Quantities ===
     type freight_group  day  quantity
   0  ltl           fg1    2    4000.0
   1  ltl           fg2    2    5000.0
   ```

   The formulation printed above the solve result is trimmed here, and so are the inventory-level and arrival-day tables that the report also prints. The report checks the solve's termination status and stops unless it is `OPTIMAL`. Both freight groups ship less-than-truckload on day 2 (zero truckload trucks); see `runbook.md` for the full inventory and arrival-day tables.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.SUPPLY_CHAIN_TRANSPORT_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The first command lists the model's objects without dropping anything; the second drops them and keeps the two schemas.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── model/
│   └── __init__.py
├── queries/
│   └── transport_plan.py
└── data/
    └── freight_groups.csv
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.transport_plan` for the full formulation and solve end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is synthetic and illustrative -- a minimal two-group example designed to teach the formulation on a Snowflake-connected RAI account, not to match a specific shipper's freight book. The transport modes and cost segments are defined inline in `model/__init__.py`, not loaded from CSV.

- **`freight_groups.csv`** (2 rows) -- one row per freight group, giving its inventory window (`inv_start_t` to `inv_end_t`), transport window (`tra_start_t` to `tra_end_t`), arrival window (`arr_start_t` to `arr_end_t`), and starting inventory weight (`inv_start`).

## Model overview

The formulation is built on three concepts: the freight groups loaded from CSV, and the transport types and LTL cost segments defined inline in `model/__init__.py`.

- **Key entities**: `FreightGroup` — a batch of freight with its own inventory, transport, and arrival time windows (the optimization solves for its per-day inventory, shipment quantities, and arrival day); `TransportType` — a shipping mode (truckload or less-than-truckload), with its transit time; `LTLSegment` — a breakpoint in the piecewise-linear less-than-truckload cost curve.
- **Primary identifiers**: `name` on `FreightGroup` and `TransportType`; integer `seg` on `LTLSegment`.
- **Important invariants**: window start days are less than or equal to window end days; `inv_start` weights are non-negative; transport-mode indicators and segment activation variables are binary; each freight group ships all inventory out by the end of its inventory window.

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

```text
CSV freight groups + inline modes/segments → decision variables → inventory + mode + arrival constraints → cost objective → solve
```

**1. Define freight groups with time windows.** Each freight group loads from CSV with its inventory, transport (departure), and arrival deadline windows plus a starting inventory weight.

**2. Define transport types and LTL cost segments.** The two shipping modes -- truckload (TL, 2-day transit) and less-than-truckload (LTL, 3-day transit) -- are defined inline, along with the LTL cost-curve breakpoints. TL carries a flat per-truck fixed cost; LTL is priced as a piecewise-linear curve the solver walks up as volume grows.

**3. Formulate decision variables.** The solve determines per-day inventory levels, per-mode shipment quantities, binary mode indicators, computed arrival days, and the piecewise LTL segment variables -- indexed over each group's own time windows.

**4. Add constraints.** Multi-period inventory flow conservation ties each day's inventory to the next day's plus what ships out; big-M coupling links the binary mode indicator to shipment volume; segment-activation logic enforces the LTL piecewise cost; and arrival days derived from departure day plus transit time must land within each group's arrival window.

**5. Minimize total cost.** The objective combines inventory holding cost, TL fixed cost, and piecewise LTL variable cost, and the MIP is solved end to end.

For the implementation, see `model/__init__.py`; to reproduce it step by step with the RAI skills, follow `runbook.md`.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace `data/freight_groups.csv` with your own; keep the column names listed in *Sample data* above.
- Ensure each group's windows are internally consistent (start day less than or equal to end day) and that the arrival window is reachable given transit times.

### Tune parameters

- **Cost parameters** -- change `inv_cost`, `tl_tra_cost`, or the LTL segment costs and limits in `model/__init__.py`.
- **Transit times** -- adjust the inline `transit_time` values on the `tl` and `ltl` transport types.

### Extend the model

- Add more freight groups by extending `freight_groups.csv` with additional rows and time windows.
- Add more LTL segments by defining additional `LTLSegment` instances for finer cost granularity.
- Extend to multiple origins/destinations by adding location concepts and routing constraints.
- Add capacity constraints on warehouses or transport links.

### Scale up / productionize

- Replace the CSV load with `model.data(snowflake_table)` for a Snowflake-backed freight book.
- The formulation scales to many freight groups within the prescriptive engine's solve budget; pin the SDK version for reproducible runs.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- Verify that each freight group's transport window overlaps with the departure days (1-4).
- Check that arrival windows are reachable given transit times (TL=2, LTL=3 days).
- Ensure `inv_start` values are positive and time windows are consistent (start <= end).

</details>

<details>
  <summary>Import error for <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.

</details>

<details>
  <summary>Authentication or configuration errors</summary>

- Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4).
- If you have multiple profiles, set `export RAI_PROFILE=<your_profile>`.

</details>

<details>
  <summary>Unexpected cost values</summary>

- The LTL cost is piecewise: the first 6000 lbs cost $0.18/lb, the next 7000 lbs cost $0.12/lb.
- TL has a flat $2000 per truck with a 24,000 lb capacity.
- Inventory holding is 0.1% of weight per day. Double-check that your freight weights match expectations.

</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) -- `model.where(...)` / `aggs` / `.define()`.
- [Ontology modeling](https://docs.relational.ai/) -- concepts, properties, and inline instances.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) -- `Problem` API, decision variables, constraints, and objective.
- [Mixed-integer programming patterns](https://docs.relational.ai/) -- binary coupling, big-M constraints, and piecewise-linear costs.

## Support

- File issues at the RelationalAI templates repository.
