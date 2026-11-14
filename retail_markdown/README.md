---
title: "Retail Markdown"
description: "Set discount levels across weeks to maximize revenue while clearing inventory."
featured: false
experience_level: intermediate
industry: "Retail & Consumer"
reasoning_types:
  - Prescriptive
tags:
  - Mixed-Integer Programming
  - Revenue Maximization
  - Inventory Management
  - Pricing Optimization
---

## What this template is for

Retailers often face the challenge of clearing seasonal inventory before it loses value. Markdown optimization determines the best discount schedule across a planning horizon to maximize total revenue -- including both sales revenue and the salvage value of any remaining stock. Discounts stimulate demand but reduce per-unit revenue, so the trade-off must be carefully balanced.

This template finds the discount schedule that maximizes revenue across a multi-week horizon, respecting a price ladder (discounts only deepen over time) and finite inventory, and crediting the salvage value of whatever is left at the end. It captures the full trade-off between aggressive discounting to drive volume and preserving margin on high-value items.

**The reasoning approach uses prescriptive optimization: a mixed-integer program that picks one discount level per product-week and tracks the resulting sales and cumulative inventory.**

## Who this is for

- Retail pricing and merchandising analysts optimizing markdown schedules
- Operations researchers working with mixed-integer programming
- Data scientists exploring multi-period optimization with binary decisions
- **Assumed knowledge**: comfortable reading Python; the pricing and optimization terms are explained as they come up

## What you'll build

- A revenue-maximizing markdown schedule (one discount level per product per week), produced by **prescriptive reasoning** (mixed-integer program)
- A price ladder that prevents discounts from reversing week to week
- A demand model combining base demand, discount lift, and weekly seasonal multipliers
- Per-week sales and cumulative-inventory tracking, bounded so cumulative sales never exceed initial stock
- A total-revenue figure that credits end-of-horizon salvage value on unsold units

## What's included

- `model/__init__.py` -- The MIP model with discount selection, sales tracking, and revenue optimization; `rai models deploy --path model` deploys it to your Snowflake account, where each refresh runs the solve
- `queries/markdown_plan.py` -- Prints the report from the deployed model: the solve's status and objective and the discount, sales, and cumulative-sales tables
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/products.csv` -- Products with initial price, cost, inventory, base demand, and salvage rate
- `data/discounts.csv` -- Discount levels with percentage and demand lift factor
- `data/weeks.csv` -- Planning weeks with seasonal demand multipliers
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (Quickstart step 4 below covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python >= 3.10

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, the one-time model deployment setup, and a Snowflake user that holds the model role.

Before the first deploy, create this template's internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.RETAIL_MARKDOWN_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.RETAIL_MARKDOWN_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.RETAIL_MARKDOWN_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.RETAIL_MARKDOWN_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.RETAIL_MARKDOWN_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.RETAIL_MARKDOWN_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.RETAIL_MARKDOWN_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.RETAIL_MARKDOWN_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model and query it:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/retail_markdown.zip), unzip it, and enter the template directory:

   ```bash
   unzip retail_markdown.zip
   cd retail_markdown
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
       name: retail_markdown_solver            # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.RETAIL_MARKDOWN               # published views and tables
     identity:
       internal_schema: <DB>.RETAIL_MARKDOWN_META      # solver inputs, results, refresh procedures
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
   python -m queries.markdown_plan
   ```

   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 23374.65

   Status: OPTIMAL
   Total revenue (sales + salvage): $23374.65

   === Selected Discounts by Product-Week ===
       product  week  discount_pct
   0    Jacket     1          20.0
   1    Jacket     2          20.0
   2    Jacket     3          20.0
   3    Jacket     4          20.0
   ...
   ```

   The formulation printed above the solve result is trimmed here, and the selected discounts are cut after four rows; the report also prints the units sold and the cumulative sales for each product and week. The report checks the solve's termination status and stops unless it is `OPTIMAL`. Discounts start shallow (20 percent) and deepen to 30 percent later in the season; no product needs the 50 percent tier. See `runbook.md` for the full discount, sales, and cumulative-sales schedule.

   To solve again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.RETAIL_MARKDOWN_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
retail_markdown/
├── README.md            # this file
├── pyproject.toml       # dependencies
├── runbook.md           # analyst-facing walkthrough
├── model/
│   └── __init__.py      # the deployed model (MIP, solve)
├── queries/
│   └── markdown_plan.py # report from the deployed model (result tables)
└── data/
    ├── products.csv     # products with price, cost, inventory, base demand, salvage rate
    ├── discounts.csv    # discount levels with percentage and demand lift
    └── weeks.csv        # planning weeks with seasonal demand multipliers
```

**Start here**: deploy with `rai models deploy --path model` and run `python -m queries.markdown_plan` for the full run end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is small and illustrative — a short seasonal clearance across a handful of products, sized so the model solves instantly while showing the full workflow.

- **`products.csv`** — one row per product, with `initial_price`, `cost`, `initial_inventory`, `base_demand` (units per week at full price), and `salvage_rate` (fraction of price recovered on leftovers).
- **`discounts.csv`** — one row per discount tier, with `discount_pct` (percent off) and `demand_lift` (demand multiplier at that discount). Includes a `level` 0 / 0% tier so "no markdown" is always an option.
- **`weeks.csv`** — one row per planning week, with `demand_multiplier` (seasonal factor applied to base demand).

## Model overview

- **Key entities**: `Product` — an item to mark down, with its price, cost, stock, demand, and salvage economics; `Discount` — a discount tier defining how much price is cut and how much demand rises; `Week` — a period in the planning horizon, with its seasonal demand factor.
- **Primary identifiers**: string `name` on `Product`; integer `level` on `Discount`; integer `num` on `Week`.
- **Important invariants**: exactly one discount level is active per product-week; discounts can only deepen over successive weeks (price ladder); cumulative sales never exceed `initial_inventory`; `discount_pct`, `demand_lift`, and `demand_multiplier` are non-negative; the selection variable is binary and sales variables are non-negative.

For the full concept and property definitions, see `model/__init__.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline loads products, discount tiers, and planning weeks, then builds a single mixed-integer program that chooses a discount for each product-week, tracks the resulting sales and inventory, and credits salvage value on whatever is left over.

```text
CSV inputs → load Product / Discount / Week → decision variables (discount choice, sales, cumulative sales)
  → one-discount + price-ladder + inventory constraints → maximize sales revenue + salvage → solve → schedule
```

1. **Load the data.** Products carry price, cost, starting inventory, base demand, and a salvage rate; discounts carry a percent-off and a demand-lift multiplier (including a 0% tier so "no markdown" is always available); weeks carry a seasonal demand multiplier.
2. **Set up the decisions.** Three variable families capture the plan: a binary choice of which discount is active for each product-week, continuous units sold per product-week-discount, and cumulative units sold through each week. A `num_weeks` count marks the final week for the salvage term.
3. **Constrain the schedule.** Exactly one discount level is active per product-week; discounts can only deepen from one week to the next (the price ladder); and cumulative sales can never exceed starting inventory.
4. **Maximize revenue.** The objective adds sales revenue — discounted price times units sold — to the salvage value of unsold units at the end of the horizon, and the solver returns the revenue-maximizing discount schedule.

See `model/__init__.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the column names listed in *Sample data* above.
- Keep a `level` 0 / 0% row in `discounts.csv` so "no markdown" remains a feasible choice.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)`.

### Tune parameters

- **Discount levels** — modify `discounts.csv` to add finer or coarser tiers with different demand lifts.
- **Planning horizon** — add or remove rows in `weeks.csv`; the model scales with longer horizons.
- **Solver time limit** — `time_limit_sec` (default `60`) on the `problem.configure(...)` call.

### Extend the model

- **Minimum margin constraint** — add a constraint ensuring the discounted price always exceeds the product cost.
- **Category-level constraints** — group products by category and limit the total discount budget per category.
- **Demand elasticity** — replace the fixed demand lift with a price-elasticity function for more realistic demand modeling.

### Scale up / productionize

- Replace the CSV bundle with ingestion from your merchandising or point-of-sale tables.
- Mixed-integer programs grow harder with more products, weeks, and discount tiers; give the solver more time via `time_limit_sec`, or accept a near-optimal solution by checking the MIP gap.

## Troubleshooting

<details>
<summary>Problem is infeasible</summary>

Check that initial inventory is sufficient for at least one week of base demand. Also verify that the discount levels include a 0% option (no discount) so the model has a feasible starting point.
</details>

<details>
<summary>Solver is slow or times out</summary>

Mixed-integer programs can be computationally expensive. Reduce the number of products, weeks, or discount levels. You can also increase `time_limit_sec` or accept a near-optimal solution by checking the MIP gap.
</details>

<details>
<summary>Connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Re-create `raiconfig.yaml` with the configuration builder (Quickstart step 4) and verify the connection settings.
</details>

<details>
<summary>ModuleNotFoundError for relationalai</summary>

Make sure you activated the virtual environment and ran `python -m pip install .` from the template directory. The `pyproject.toml` declares the required dependencies.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — `model.where(...)`, `.per(...)`, aggregations, and `model.select(...)`.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives.

### Deeper dives

- [Multi-period optimization patterns](https://docs.relational.ai/) — modeling week-over-week state (cumulative sales, price ladders) with indexed decision variables.

## Support

- File issues at the RelationalAI templates repository.
