---
title: "Campaign ROI"
description: "Reallocate marketing campaign budgets across regions to maximize conversions, with per-campaign floor and cap constraints and a regional cap on a paused region."
featured: false
experience_level: beginner
industry: "Marketing"
reasoning_types:
  - Prescriptive
tags:
  - Linear Programming
  - Marketing
  - Budget Reallocation
  - Regional Cap
  - Conversion Maximization
---

# Campaign ROI

## What this template is for

This template uses **Prescriptive** reasoning to reallocate a marketing budget across an existing portfolio of campaigns to maximize total expected conversions, subject to three real-world constraints:

- **Per-campaign floor** — no campaign can drop below a fixed fraction of its current spend (institutional inertia: account managers, vendor commitments, brand presence).
- **Per-campaign cap** — no campaign can exceed a multiple of its current spend (creative-fatigue, audience-saturation guardrails).
- **Regional cap** — total spend in one designated *paused* region cannot exceed a configurable share of the total budget (organizational pause: regulatory, reputational, or capacity reasons).

The decision: pick a new dollar budget for every campaign such that total spend respects the overall budget, every campaign respects its floor and cap, the paused region stays within its share, and total expected conversions are maximized.

This is the **portfolio rebalancing** counterpart to [`ad_spend_allocation`](../ad_spend_allocation/), which decides spend across channel × campaign pairs from scratch. Here the question is "we have a working portfolio — where should the next dollar go?" rather than "design the portfolio from zero."

## Who this is for

- Marketing analytics teams reshaping campaign portfolios under fixed quarterly budgets
- Operations researchers learning continuous LP with bound constraints derived from per-entity data
- Data scientists exploring the floor-cap-regional-cap pattern that recurs across portfolio decisions (advertising, R&D, vendor allocation)

## What you'll build

- A continuous LP that reallocates budget across 12 marketing campaigns
- Per-campaign floor and cap bounds derived from each campaign's current spend
- A total budget constraint
- A regional cap constraint that limits the paused region's share of total spend
- An objective that maximizes total expected conversions = `sum(budget × conversion_rate)`

## What's included

- `campaign_roi.py` — main script (single end-to-end run)
- `data/campaigns.csv` — 12 campaigns across 5 regions with current budgets and conversion rates
- `pyproject.toml` — Python package configuration with dependencies

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) == 1.0.14

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

4. Configure Snowflake connection and RAI profile:

   ```bash
   rai init
   ```

5. Run the template:

   ```bash
   python campaign_roi.py
   ```

6. Expected output (truncated):

   ```text
   Status: OPTIMAL
   Total expected conversions (optimized): 3,151.1
   Total expected conversions (current):   2,691.0
   Lift: +17.1%

   Budget reallocation per campaign (sorted by largest absolute change):
                   campaign  region  current  optimized  rate  delta  multiple
       WEST_Premium_Upgrade    WEST     80.0      240.0   3.2  160.0     3.000
          SOUTH_Retention_4   SOUTH    160.0       16.0   2.2 -144.0     0.100
        CENTRAL_Retention_3 CENTRAL     70.0      210.0   2.7  140.0     3.000
          CENTRAL_WinBack_7 CENTRAL    140.0       14.0   2.3 -126.0     0.100
   WEST_Retention_Emergency    WEST    200.0      325.0   2.9  125.0     1.625
            SOUTH_WinBack_6   SOUTH     50.0      150.0   2.6  100.0     3.000
   ...

   Regional spend (optimized):
    region  current  optimized  share_of_total
      WEST    280.0      565.0        0.500000
   CENTRAL    260.0      229.0        0.202655
     SOUTH    250.0      170.0        0.150442
     NORTH    140.0      146.0        0.129204
      EAST    200.0       20.0        0.017699

   Paused region 'WEST' cap: 565.0 (50% of $1,130K total)
   ```

   The optimum hits the WEST regional cap exactly (50% of $1,130K = $565K), reaches the 3× cap on three high-performing campaigns (`WEST_Premium_Upgrade`, `CENTRAL_Retention_3`, `SOUTH_WinBack_6`), and pushes six low-performing campaigns down to the 10% floor. Despite holding total spend constant, conversions increase by 17.1%.

## Template structure

```text
.
├── README.md               # this file
├── pyproject.toml          # dependencies
├── campaign_roi.py         # main script (end-to-end)
└── data/
    └── campaigns.csv       # 12 campaigns across 5 regions
```

**Start here:** `python campaign_roi.py`.

## Sample data

12 marketing campaigns across 5 regions (NORTH, SOUTH, CENTRAL, EAST, WEST). Each campaign has:

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `name` | String | Campaign name (region prefix + type + id) |
| `region` | String | Region tag — drives the regional-cap constraint |
| `current_budget` | Float | Current spend in $K |
| `conversion_rate` | Float | Conversions per $K (empirical, varies 1.5 to 3.2) |

Total current budget across all campaigns: $1,130K. WEST has the two highest-rate campaigns (3.2 and 2.9) — without the regional cap, the optimum would push almost all budget into WEST.

## Model overview

### Campaign

A marketing campaign with a current budget, region tag, and an empirical conversion rate.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/campaigns.csv` |
| `name` | String | No | Human-readable name |
| `region` | String | No | One of NORTH / SOUTH / CENTRAL / EAST / WEST |
| `current_budget` | Float | No | Current spend in $K |
| `conversion_rate` | Float | No | Conversions per $K of spend |

## How it works

### 1. Decision variable

A continuous budget variable per campaign. The lower bound 0 is permissive — the per-campaign floor (below) tightens it from the data.

```python
Campaign.x_budget = model.Property(f"{Campaign} has new budget {Float:budget}")

problem.solve_for(
    Campaign.x_budget,
    lower=0,
    name=["budget", Campaign.name],
)
```

### 2. Constraints

**Per-campaign floor and cap**, derived from each campaign's current spend:

```python
problem.satisfy(model.require(
    Campaign.x_budget >= FLOOR_FRACTION * Campaign.current_budget,
    Campaign.x_budget <= CAP_MULTIPLIER * Campaign.current_budget,
))
```

**Total budget**:

```python
problem.satisfy(model.require(sum(Campaign.x_budget) <= TOTAL_BUDGET))
```

**Paused-region cap** — single constraint summing only campaigns in the paused region:

```python
problem.satisfy(model.require(
    sum(Campaign.x_budget).where(Campaign.region == PAUSED_REGION)
    <= PAUSED_CAP_FRACTION * TOTAL_BUDGET
))
```

### 3. Objective

```python
problem.maximize(sum(Campaign.x_budget * Campaign.conversion_rate))
```

## Customize this template

### Use your own data

Replace `data/campaigns.csv` with your own. Required columns: `id`, `name`, `region`, `current_budget`, `conversion_rate`. The model loads region as a free string — any region naming convention works.

### Tune parameters

All four are at the top of the script under `# Configure inputs`:

| Parameter | Default | Effect |
|---|---|---|
| `TOTAL_BUDGET` | 1130 ($K) | Cap on total spend across all campaigns |
| `FLOOR_FRACTION` | 0.10 | Each campaign cannot drop below 10% of current |
| `CAP_MULTIPLIER` | 3.0 | Each campaign cannot exceed 3× current |
| `PAUSED_REGION` | `"WEST"` | Which region is subject to the share cap |
| `PAUSED_CAP_FRACTION` | 0.5 | Paused region cannot exceed 50% of total spend |

Tightening `CAP_MULTIPLIER` toward 1.5 will distribute increases across more campaigns. Loosening `FLOOR_FRACTION` toward 0 lets the optimizer fully shut down poor performers.

### Extend the model

- **Conversion saturation.** The current model assumes linear conversions (each $1K adds the same number of conversions). For more realistic diminishing returns, replace `Campaign.conversion_rate` with a piecewise-linear or logarithmic function and add SOS2 constraints. See `traveling_salesman` and `supply_chain_transport` for piecewise-linear examples in this portfolio.
- **Multiple paused regions.** Generalize the regional cap to a parameterized `RegionCap` concept and apply the constraint per region.
- **Forecast uncertainty.** Add a Scenario Concept with conversion-rate multipliers (low / base / high) and solve all scenarios in one pass — see `ad_spend_allocation` for the Scenario pattern.

## Troubleshooting

<details>
  <summary>Why is the WEST allocation exactly $565K?</summary>

  WEST has the two highest conversion rates (3.2 and 2.9). Without the regional cap, the optimum would push WEST_Premium_Upgrade to its 3× cap ($240K) and WEST_Retention_Emergency toward its 3× cap ($600K), totaling $840K. The 50% regional cap binds at $565K, so the optimizer fills WEST_Premium_Upgrade to its 3× cap first (highest rate) and then takes WEST_Retention_Emergency up to $325K to exactly hit the regional cap.
</details>

<details>
  <summary>Why does the total optimized budget exactly equal TOTAL_BUDGET?</summary>

  Because every campaign has a positive conversion rate, the maximization objective always benefits from spending more. The total budget constraint binds at the upper limit. If you want to allow under-spending, change the objective to penalize unspent budget, or change the budget constraint from `<=` to `==`.
</details>

<details>
  <summary>Why are six campaigns at exactly 10% of current?</summary>

  These are campaigns whose conversion rates are below the marginal rate of the binding budget constraint. The optimizer can't fully shut them down because the floor constraint forces 10%. If you set `FLOOR_FRACTION = 0`, those campaigns would go to zero.
</details>

<details>
  <summary>The optimizer returns INFEASIBLE.</summary>

  The most likely cause is that the floor sums exceed the total budget. Check: `sum(FLOOR_FRACTION * current_budget for all campaigns) <= TOTAL_BUDGET`. Loosen the floor or raise the total budget.
</details>

## Related templates

- [`ad_spend_allocation`](../ad_spend_allocation/) — channel × campaign spend from scratch (designs the portfolio rather than rebalancing it)
- [`portfolio_balancing`](../portfolio_balancing/) — financial portfolio rebalancing with rules, graph clustering, and bi-objective Markowitz
- [`hospital_staffing`](../hospital_staffing/) — bi-objective LP for resource allocation under multiple competing goals
