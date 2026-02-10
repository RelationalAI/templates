---
title: "Ad Spend Allocation"
description: "Allocate a fixed budget across channel–campaign combinations to maximize expected conversions, subject to channel spend bounds and per-campaign budget limits."
featured: false
experience_level: intermediate
industry: "Marketing"
reasoning_types:
  - Prescriptive
tags:
  - Allocation
  - MILP
---

# Ad Spend Allocation

Marketing teams must distribute limited advertising budgets across multiple channels (Search, Social, Display, Video, Email) and campaigns to maximize return on investment.
This template models allocating spend across 5 channels and 3 campaigns, where each channel-campaign combination has different conversion effectiveness.
The challenge is that each channel has minimum spend thresholds (you can't spend just $10 on a channel—there are setup costs) and maximum caps, while campaign budgets constrain total spend.

This templates uses RelationalAI's **prescriptive reasoner** to find the best allocation of spend across channel-campaign pairs to maximize total expected conversions, while respecting these constraints.
This helps you:

- **Improve ROAS**: Achieve higher Return on Ad Spend compared to manual allocation or simple rules
- **Budget efficiency**: Eliminate waste from over-allocating to saturated channels while identifying under-invested opportunities
- **Make data-driven decisions**: Replace gut-feel allocation with mathematically optimal distribution based on measured conversion rates

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and linear/mixed-integer optimization concepts.

## What you’ll build / learn

- Model business entities (channels, campaigns) as concepts with properties.
- Define decision variables (continuous spend + binary “active” flags).
- Add constraints (min/max spend, campaign budgets, minimum coverage).
- Solve with the **HiGHS** backend and inspect allocations.

## What’s included

- **Model + solve script**: `ad_spend_allocation.py`
- **Sample data**: `data/channels.csv`, `data/campaigns.csv`, `data/effectiveness.csv`
- **Python dependencies**: `pyproject.toml`
- **Outputs**: prints solver status, objective value, and spend allocation table for each budget scenario

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

2. **Install dependencies**

   From this folder:

   ```bash
   python -m pip install -e .
   ```

3. **Configure Snowflake connection and RAI profile**

   ```bash
   rai init
   ```

4. **Run the template**

   ```bash
   python ad_spend_allocation.py
   ```

5. **Expected output**

   The script solves three budget scenarios. Decision variables shown for the baseline scenario (total_budget = 45000). The summary below shows objectives for all scenarios.

   ```text
   Running scenario: total_budget = 45000
     Status: OPTIMAL, Objective: 3430.0

     Spend allocation:
                           name   value
    spend_Email_Brand_Awareness  2000.0
      spend_Email_Seasonal_Sale  2000.0
   spend_Search_Brand_Awareness  5000.0
    spend_Search_Product_Launch 10000.0
     spend_Search_Seasonal_Sale  8000.0
   spend_Social_Brand_Awareness  8000.0
     spend_Video_Product_Launch 10000.0

   ==================================================
   Scenario Analysis Summary
   ==================================================
     35000: OPTIMAL, obj=2880.0
     45000: OPTIMAL, obj=3430.0
     55000: OPTIMAL, obj=3430.0
   ```

## Repository structure

```text
.
├─ README.md
├─ pyproject.toml
├─ ad_spend_allocation.py
└─ data/
   ├─ channels.csv
   ├─ campaigns.csv
   └─ effectiveness.csv
```

**Start here**: `ad_spend_allocation.py`

## Sample data

Data files are in `data/`.

### `channels.csv`

| Column | Meaning |
| --- | --- |
| `id` | Unique channel identifier |
| `name` | Channel name (e.g., Search, Social) |
| `min_spend` | Minimum spend if the channel is active |
| `max_spend` | Maximum spend allowed |
| `roi_coefficient` | Additional channel attribute (not used in the objective in this template) |

### `campaigns.csv`

| Column | Meaning |
| --- | --- |
| `id` | Unique campaign identifier |
| `name` | Campaign name |
| `budget` | Total spend allowed for the campaign |
| `target_conversions` | Campaign attribute (not used as a constraint in this template) |

### `effectiveness.csv`

| Column | Meaning |
| --- | --- |
| `channel_id` | Foreign key to `channels.csv.id` |
| `campaign_id` | Foreign key to `campaigns.csv.id` |
| `conversion_rate` | Expected conversions per $ spent |

## Model overview

The semantic model for this template is built around four concepts.

### `Channel`

A marketing channel (e.g., Search, Social) with spend bounds used to constrain the optimization.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/channels.csv` |
| `name` | string | No | Human-readable channel name |
| `min_spend` | float | No | Minimum spend if the channel is active |
| `max_spend` | float | No | Maximum spend allowed (per allocation) |
| `roi_coefficient` | float | No | Included in sample data; not used in the objective in this template |

### `Campaign`

A marketing campaign with a budget constraint applied during optimization.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `id` | int | Yes | Loaded as the key from `data/campaigns.csv` |
| `name` | string | No | Human-readable campaign name |
| `budget` | float | No | Upper bound on total spend across all channels for the campaign |
| `target_conversions` | float | No | Included in sample data; not enforced as a constraint in this template |

### `Effectiveness`

A channel–campaign pair with an expected conversion rate used in the objective.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `channel` | `Channel` | Part of compound key | Joined via `data/effectiveness.csv.channel_id` |
| `campaign` | `Campaign` | Part of compound key | Joined via `data/effectiveness.csv.campaign_id` |
| `conversion_rate` | float | No | Expected conversions per $ spent |

### `Allocation`

A decision concept created for each `Effectiveness` row; the solver chooses `spend` and `active`.

| Property | Type | Identifying? | Notes |
| --- | --- | --- | --- |
| `effectiveness` | `Effectiveness` | Yes | One allocation per channel–campaign pair |
| `spend` | float | No | Continuous decision variable ($\ge 0$) |
| `active` | float | No | Binary decision variable (0/1) |

## How it works

This section walks through the highlights in `ad_spend_allocation.py`.

### 1) Create a model and load inputs

The template builds a Semantics `Model`, defines concepts + properties, and loads CSVs into those concepts.

```python
model = Model("ad_spend", use_lqp=False)

Channel = model.Concept("Channel")
Channel.id = model.Property("{Channel} has {id:int}")
Channel.name = model.Property("{Channel} has {name:string}")
Channel.min_spend = model.Property("{Channel} has {min_spend:float}")
Channel.max_spend = model.Property("{Channel} has {max_spend:float}")
Channel.roi_coefficient = model.Property("{Channel} has {roi_coefficient:float}")
data(read_csv(DATA_DIR / "channels.csv")).into(Channel, keys=["id"])

Campaign = model.Concept("Campaign")
Campaign.id = model.Property("{Campaign} has {id:int}")
Campaign.name = model.Property("{Campaign} has {name:string}")
Campaign.budget = model.Property("{Campaign} has {budget:float}")
Campaign.target_conversions = model.Property("{Campaign} has {target_conversions:int}")
data(read_csv(DATA_DIR / "campaigns.csv")).into(Campaign, keys=["id"])
```

### 2) Build channel-campaign effectiveness rows

`effectiveness.csv` contains foreign keys (`channel_id`, `campaign_id`). The template resolves them into `Channel` and `Campaign` instances and creates an `Effectiveness` concept per row.

```python
Effectiveness = model.Concept("Effectiveness")
Effectiveness.channel = model.Property("{Effectiveness} via {channel:Channel}")
Effectiveness.campaign = model.Property("{Effectiveness} for {campaign:Campaign}")
Effectiveness.conversion_rate = model.Property("{Effectiveness} has {conversion_rate:float}")

eff_data = data(read_csv(DATA_DIR / "effectiveness.csv"))
where(Channel.id == eff_data.channel_id, Campaign.id == eff_data.campaign_id).define(
    Effectiveness.new(channel=Channel, campaign=Campaign, conversion_rate=eff_data.conversion_rate)
)
```

### 3) Define decision variables and solve per scenario

An `Allocation` decision concept is created for every `Effectiveness` row. The script then loops over budget scenarios, creating a fresh `SolverModel` for each.

```python
Allocation = model.Concept("Allocation")
Allocation.effectiveness = model.Property("{Allocation} uses {effectiveness:Effectiveness}")
Allocation.spend = model.Property("{Allocation} has {spend:float}")
Allocation.active = model.Property("{Allocation} is {active:float}")
model.define(Allocation.new(effectiveness=Effectiveness))

SCENARIO_VALUES = [35000, 45000, 55000]

for scenario_value in SCENARIO_VALUES:
    total_budget = scenario_value
    solver_model = SolverModel(model, "cont")

    # `spend` is continuous with a lower bound of 0.
    solver_model.solve_for(
        Allocation.spend,
        name=["spend", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name],
        lower=0,
    )

    # `active` is a binary variable (0 or 1).
    solver_model.solve_for(
        Allocation.active,
        type="bin",
        name=["active", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name],
    )
```

### 4) Add constraints

Each scenario iteration adds the same structural constraints, plus a total budget constraint parameterized by the scenario value.

```python
    # Spend bounded by per-channel min/max when active.
    solver_model.satisfy(require(
        Allocation.spend >= Allocation.effectiveness.channel.min_spend * Allocation.active
    ))
    solver_model.satisfy(require(
        Allocation.spend <= Allocation.effectiveness.channel.max_spend * Allocation.active
    ))

    # Per-campaign budget across all channels.
    campaign_spend = sum(Allocation.spend).where(
        Allocation.effectiveness.campaign == Campaign
    ).per(Campaign)
    solver_model.satisfy(require(campaign_spend <= Campaign.budget))

    # At least one active channel per campaign.
    campaign_channels = sum(Allocation.active).where(
        Allocation.effectiveness.campaign == Campaign
    ).per(Campaign)
    solver_model.satisfy(require(campaign_channels >= 1))

    # Total budget across all campaigns (scenario parameter).
    solver_model.satisfy(require(sum(Allocation.spend) <= total_budget))
```

### 5) Maximize conversions and extract results

The objective is linear in spend: maximize $\sum spend \cdot conversion\_rate$. After solving, `variable_values()` extracts the solution directly from the solver.

```python
    total_conversions = sum(Allocation.spend * Allocation.effectiveness.conversion_rate)
    solver_model.maximize(total_conversions)

    solver_model.solve(Solver("highs"), time_limit_sec=60)

    # Extract spend allocation from solver results
    var_df = solver_model.variable_values().to_df()
    spend_df = var_df[var_df["name"].str.startswith("spend") & (var_df["float"] > 0.001)].rename(columns={"float": "value"})
```

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the same column names (or update the loading logic in `ad_spend_allocation.py`).
- Ensure that `effectiveness.csv` only references valid `channel_id` and `campaign_id` values.

### Tune parameters

- **Solver**: the template uses `Solver("highs")`.
- **Time limit**: `time_limit_sec=60` in the call to `s.solve(...)`.

### Extend the model

- Add per-channel total spend limits across all campaigns.
- Add campaign conversion targets as constraints (using `Campaign.target_conversions`).
- Add diminishing returns (piecewise linear approximations) if conversion rate decreases with spend.

### Scale up / productionize

- Replace CSV ingestion with Snowflake sources.
- Write allocations back to Snowflake after solving.

## Troubleshooting

<details>
  <summary>Why does authentication/configuration fail?</summary>


- Run `rai init` to create/update `raiconfig.toml`.
- If you have multiple profiles, set `RAI_PROFILE` or switch profiles in your config.

</details>

<details>
  <summary>Why does the script fail to connect to the RAI Native App?</summary>


- Verify the Snowflake account/role/warehouse and `rai_app_name` are correct in `raiconfig.toml`.
- Ensure the RAI Native App is installed and you have access.

</details>

<details>
  <summary>Why do I get <code>Status: INFEASIBLE</code>?</summary>


- Check that each campaign budget is high enough to pay for at least one active channel's `min_spend`.
- Check that channel `min_spend` values are not greater than `max_spend`.
- Confirm conversion rates are present for each campaign (missing effectiveness rows reduce options).

</details>

<details>
  <summary>Why is the spend allocation empty?</summary>


- The script filters allocations with `Allocation.spend > 0.001`. If everything is near zero, inspect constraints and budgets.
- Confirm input CSVs were read correctly and contain rows.

</details>

## Scenario Analysis

This template includes **budget sensitivity analysis** — how does a company-wide marketing budget cap affect total conversions?

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `total_budget` | Numeric | `35000`, `45000`, `55000` | Total budget across all campaigns |

The $45k and $55k scenarios produce the same objective (3,430) because per-campaign budgets ($15k + $20k + $10k = $45k) already cap total spend — the $55k total budget is non-binding. At $35k (-16%), the binding total budget forces cuts to lower-converting allocations.

---

## Next steps

- Add scenario parameters (e.g., channel saturation, campaign priorities) and compare solutions.
- Persist the results (CSV or Snowflake table) and build a small dashboard.
- Extend the objective (e.g., weighted conversions, CAC/ROAS trade-offs).
