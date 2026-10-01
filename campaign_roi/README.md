---
title: "Campaign ROI"
description: "Reallocate marketing campaign budgets across regions to maximize conversions, with per-campaign floor and cap constraints and a regional cap on a paused region."
featured: false
experience_level: beginner
industry: "Retail & Consumer"
reasoning_types:
  - Prescriptive
tags:
  - Linear Programming
  - Marketing
  - Budget Reallocation
  - Regional Cap
  - Conversion Maximization
---

## What this template is for

Every marketing team eventually faces the same question: the portfolio of campaigns is already running and the quarterly budget is fixed, so where should the next dollar go? Some campaigns convert far better than others, but you cannot simply pour everything into the winners. Account managers, vendor commitments, and brand presence set a floor under each campaign; creative fatigue and audience saturation set a cap; and a region under an organizational pause (regulatory, reputational, or capacity reasons) can only absorb so much of the total. Return on investment (ROI) depends on respecting all of those limits at once while still moving money toward what works.

**This template uses prescriptive reasoning to pick a new dollar budget for every campaign that maximizes total expected conversions while honoring the overall budget, each campaign's floor and cap, and the paused region's share limit.** The result is a defensible reallocation plan you can act on, not just a ranking of which campaigns look good.

## Who this is for

- Marketing analytics teams reshaping campaign portfolios under fixed quarterly budgets.
- Operations researchers learning continuous linear programming (LP) with bound constraints derived from per-entity data.
- Data scientists exploring the floor-cap-regional-cap pattern that recurs across portfolio decisions (advertising, research and development, vendor allocation).
- **Assumed knowledge**: comfortable reading Python; the LP and marketing terms are explained as they come up. No prior RelationalAI experience is required to run it.

## What you'll build

- A reallocation plan that maximizes total expected conversions across 12 marketing campaigns while holding total spend constant, produced by RelationalAI's **prescriptive reasoner**.
- Per-campaign floor and cap bounds derived automatically from each campaign's current spend, expressed as decision-variable constraints.
- A regional cap constraint that keeps the paused region within a configurable share of the total budget.
- A per-campaign, per-region summary of the optimized budget versus current spend, with the binding constraints called out.

## What's included

- **Model**: a continuous LP over a single `Campaign` concept, with per-campaign floor and cap bounds, a total-budget constraint, a paused-region share cap, and a conversion-maximizing objective.
- **Runner**: `campaign_roi.py` — a single Python script that runs end-to-end against a Snowflake-connected RAI account.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data**: `data/campaigns.csv` — 12 campaigns across 5 regions with current budgets and empirical conversion rates.
- **Outputs**: solver status, optimized-versus-current conversions and lift, a per-campaign reallocation table, and a regional-spend summary against the paused-region cap.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10.
- RelationalAI Python SDK (`relationalai == 1.0.14`).

## Quickstart

1. Download the ZIP file for this template and extract it:

   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/campaign_roi.zip
   unzip campaign_roi.zip
   cd campaign_roi
   ```

   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

3. Install dependencies:

   ```bash
   python -m pip install .
   ```

4. Configure the Snowflake connection and RAI profile:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python campaign_roi.py
   ```

6. Expected output (a few lines confirm a successful run):

   ```text
   Status: OPTIMAL
   Total expected conversions (optimized): 3,151.1
   Total expected conversions (current):   2,691.0
   Lift: +17.1%

   Paused region 'WEST' cap: 565.0 (50% of $1,130K total)
   ```

   The optimum hits the WEST regional cap exactly (50% of $1,130K = $565K), reaches the 3x cap on three high-performing campaigns (`WEST_Premium_Upgrade`, `CENTRAL_Retention_3`, `SOUTH_WinBack_6`), and pushes six low-performing campaigns down to the 10% floor. Despite holding total spend constant, conversions increase by 17.1%. The full printout, including the per-campaign reallocation table and regional-spend summary, is in `runbook.md`.

## Template structure

```text
.
├── README.md               # this file
├── pyproject.toml          # dependencies
├── runbook.md              # analyst-facing walkthrough
├── campaign_roi.py         # main script (end-to-end)
└── data/
    └── campaigns.csv       # 12 campaigns across 5 regions
```

**Start here**: run `python campaign_roi.py` for the full reallocation end to end, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

The bundled data is synthetic and illustrative — designed to teach the reallocation pattern, not to match a specific advertiser's portfolio. It describes 12 marketing campaigns across 5 regions (NORTH, SOUTH, CENTRAL, EAST, WEST). Each campaign has:

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `name` | String | Campaign name (region prefix, then type, then id) |
| `region` | String | Region tag — drives the regional-cap constraint |
| `current_budget` | Float | Current spend in $K |
| `conversion_rate` | Float | Conversions per $K (empirical, varies 1.5 to 3.2) |

Total current budget across all campaigns: $1,130K. WEST has the two highest-rate campaigns (3.2 and 2.9), so without the regional cap the optimum would push almost all budget into WEST.

## Model overview

The model is a single concept: one `Campaign` per row of `campaigns.csv`, enriched with a decision-variable property after the solve.

- **Key entities**: `Campaign` — a marketing campaign with a current budget, region tag, and empirical conversion rate; its optimized budget is the decision variable populated after the solve.
- **Primary identifiers**: integer `id` on `Campaign`, loaded from `data/campaigns.csv`.
- **Important invariants**: `current_budget` and `conversion_rate` are non-negative; the optimized budget `x_budget` stays between the per-campaign floor and cap; total spend does not exceed `TOTAL_BUDGET`; and the paused region's spend does not exceed its share cap.

For the full concept and property definitions, see `campaign_roi.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The script loads the campaigns into a single `Campaign` concept, defines one continuous decision variable per campaign, adds the floor, cap, total-budget, and regional-cap constraints, maximizes conversions, and prints the reallocation.

### 1. Decision variable

One continuous budget variable per campaign, with a permissive lower bound of 0 that the per-campaign floor (below) tightens from the data.

### 2. Constraints

The per-campaign floor and cap are derived from each campaign's current spend: the floor reflects institutional inertia (account managers, vendor commitments, brand presence), and the cap reflects creative-fatigue and audience-saturation guardrails. A total-budget constraint caps combined spend across all campaigns. The paused-region cap sums only campaigns in the paused region and keeps that total within a configurable share of the budget (an organizational pause for regulatory, reputational, or capacity reasons).

### 3. Objective

The objective maximizes total expected conversions — the sum over campaigns of budget times conversion rate.

See `campaign_roi.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

### Use your own data

Replace `data/campaigns.csv` with your own. Required columns: `id`, `name`, `region`, `current_budget`, `conversion_rate`. The model loads region as a free string, so any region naming convention works.

### Tune parameters

All parameters live at the top of the script under `# Configure inputs`:

| Parameter | Default | Effect |
|---|---|---|
| `TOTAL_BUDGET` | 1130 ($K) | Cap on total spend across all campaigns |
| `FLOOR_FRACTION` | 0.10 | Each campaign cannot drop below 10% of current |
| `CAP_MULTIPLIER` | 3.0 | Each campaign cannot exceed 3 times current |
| `PAUSED_REGION` | `"WEST"` | Which region is subject to the share cap |
| `PAUSED_CAP_FRACTION` | 0.5 | Paused region cannot exceed 50% of total spend |

Tightening `CAP_MULTIPLIER` toward 1.5 distributes increases across more campaigns. Loosening `FLOOR_FRACTION` toward 0 lets the optimizer fully shut down poor performers.

### Extend the model

- **Conversion saturation.** The current model assumes linear conversions (each $1K adds the same number of conversions). For more realistic diminishing returns, replace `Campaign.conversion_rate` with a piecewise-linear or logarithmic function and add SOS2 constraints. See `traveling_salesman` and `supply_chain_transport` for piecewise-linear examples in this portfolio.
- **Multiple paused regions.** Generalize the regional cap to a parameterized `RegionCap` concept and apply the constraint per region.
- **Forecast uncertainty.** Add a Scenario concept with conversion-rate multipliers (low / base / high) and solve all scenarios in one pass — see `ad_spend_allocation` for the Scenario pattern.

### Scale up / productionize

- For Snowflake-backed runs, swap the `read_csv(...)` call for a `model.data(snowflake_table)` call so the campaigns load directly from your warehouse.
- The LP scales comfortably to thousands of campaigns; solve time grows with the number of decision variables and constraints, not the budget size.
- Pin `relationalai` (see Prerequisites) and keep the parameters under `# Configure inputs` in version control so runs are reproducible.

## Troubleshooting

<details>
  <summary>Why is the WEST allocation exactly $565K?</summary>

  WEST has the two highest conversion rates (3.2 and 2.9). Without the regional cap, the optimum would push WEST_Premium_Upgrade to its 3x cap ($240K) and WEST_Retention_Emergency toward its 3x cap ($600K), totaling $840K. The 50% regional cap binds at $565K, so the optimizer fills WEST_Premium_Upgrade to its 3x cap first (highest rate) and then takes WEST_Retention_Emergency up to $325K to exactly hit the regional cap.
</details>

<details>
  <summary>Why does the total optimized budget exactly equal TOTAL_BUDGET?</summary>

  Because every campaign has a positive conversion rate, the maximization objective always benefits from spending more. The total budget constraint binds at the upper limit. If you want to allow under-spending, change the objective to penalize unspent budget, or change the budget constraint from `<=` to `==`.
</details>

<details>
  <summary>Why are six campaigns at exactly 10% of current?</summary>

  These are campaigns whose conversion rates are below the marginal rate of the binding budget constraint. The optimizer cannot fully shut them down because the floor constraint forces 10%. If you set `FLOOR_FRACTION = 0`, those campaigns would go to zero.
</details>

<details>
  <summary>The optimizer returns INFEASIBLE.</summary>

  The most likely cause is that the floor sums exceed the total budget. Check that the sum of `FLOOR_FRACTION * current_budget` across all campaigns is at most `TOTAL_BUDGET`. Loosen the floor or raise the total budget.
</details>

## Related templates

- [`ad_spend_allocation`](../ad_spend_allocation/) — channel-by-campaign spend from scratch (designs the portfolio rather than rebalancing it).
- [`portfolio_balancing`](../portfolio_balancing/) — financial portfolio rebalancing with rules, graph clustering, and bi-objective Markowitz.
- [`hospital_staffing`](../hospital_staffing/) — bi-objective LP for resource allocation under multiple competing goals.

## Learn more

### Core concepts

- [RelationalAI documentation](https://docs.relational.ai/) — concepts, properties, and how models load and query data.
- [Prescriptive reasoning](https://docs.relational.ai/) — the `Problem` API, decision variables, constraints, and objectives used throughout this template.

### Language / modeling reference

- [PyRel query language](https://docs.relational.ai/) — `model.define`, `model.require`, `model.select`, and aggregations such as `sum(...)`.

## Support

- File issues at the RelationalAI templates repository.
