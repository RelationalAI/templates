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

- `retail_markdown.py` -- Main script defining the MIP model with discount selection, sales tracking, and revenue optimization
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- `data/products.csv` -- Products with initial price, cost, inventory, base demand, and salvage rate
- `data/discounts.csv` -- Discount levels with percentage and demand lift factor
- `data/weeks.csv` -- Planning weeks with seasonal demand multipliers
- `pyproject.toml` -- Python package configuration with dependencies

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/retail_markdown.zip
   unzip retail_markdown.zip
   cd retail_markdown
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python retail_markdown.py
   ```

6. Expected output:
   ```text
   Status: OPTIMAL
   Total revenue (sales + salvage): $23374.65
   ```

   Discounts start shallow (20%) and deepen to 30% later in the season; no
   product needs the 50% tier. See `runbook.md` for the full discount, sales,
   and cumulative-sales schedule.

## Template structure

```text
retail_markdown/
├── README.md            # this file
├── pyproject.toml       # dependencies
├── retail_markdown.py   # main script (MIP model, solve, result tables)
├── runbook.md           # analyst-facing walkthrough
└── data/
    ├── products.csv     # products with price, cost, inventory, base demand, salvage rate
    ├── discounts.csv    # discount levels with percentage and demand lift
    └── weeks.csv        # planning weeks with seasonal demand multipliers
```

**Start here**: run `python retail_markdown.py` for the full run end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is small and illustrative — a short seasonal clearance across a handful of products, sized so the model solves instantly while showing the full workflow.

- **`products.csv`** — one row per product, with `initial_price`, `cost`, `initial_inventory`, `base_demand` (units per week at full price), and `salvage_rate` (fraction of price recovered on leftovers).
- **`discounts.csv`** — one row per discount tier, with `discount_pct` (percent off) and `demand_lift` (demand multiplier at that discount). Includes a `level` 0 / 0% tier so "no markdown" is always an option.
- **`weeks.csv`** — one row per planning week, with `demand_multiplier` (seasonal factor applied to base demand).

## Model overview

- **Key entities**: `Product` — an item to mark down, with its price, cost, stock, demand, and salvage economics; `Discount` — a discount tier defining how much price is cut and how much demand rises; `Week` — a period in the planning horizon, with its seasonal demand factor.
- **Primary identifiers**: string `name` on `Product`; integer `level` on `Discount`; integer `num` on `Week`.
- **Important invariants**: exactly one discount level is active per product-week; discounts can only deepen over successive weeks (price ladder); cumulative sales never exceed `initial_inventory`; `discount_pct`, `demand_lift`, and `demand_multiplier` are non-negative; the selection variable is binary and sales variables are non-negative.

For the full concept and property definitions, see `retail_markdown.py`; `runbook.md` builds them step by step with the RAI skills.

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

See `retail_markdown.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the column names listed in *Sample data* above.
- Keep a `level` 0 / 0% row in `discounts.csv` so "no markdown" remains a feasible choice.
- For Snowflake-backed runs, swap the `read_csv(...)` calls for `model.data(snowflake_table)`.

### Tune parameters

- **Discount levels** — modify `discounts.csv` to add finer or coarser tiers with different demand lifts.
- **Planning horizon** — add or remove rows in `weeks.csv`; the model scales with longer horizons.
- **Solver time limit** — `time_limit_sec` (default `60`) on the `problem.solve(...)` call.

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
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
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
