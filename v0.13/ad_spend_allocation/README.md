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

> [!WARNING]
> This template uses the early access `relational.semantics` API in version `0.13.3` of the `relationalai` Python package.

## What this template is for

Marketing teams must distribute limited advertising budgets across multiple channels (Search, Social, Display, Video, Email) and campaigns to maximize return on investment.
This template models allocating spend across 5 channels and 3 campaigns, where each channel-campaign combination has different conversion effectiveness.

The challenge is that each channel has minimum spend thresholds (you can't spend just $10 on a channel—there are setup costs) and maximum caps, while campaign budgets constrain total spend.
This template uses RelationalAI's **prescriptive reasoner** to find the best allocation of spend across channel-campaign pairs to maximize total expected conversions, while respecting these constraints.

Prescriptive reasoning helps you:

- **Improve ROAS**: Achieve higher Return on Ad Spend compared to manual allocation or simple rules <!-- TODO: Add % improvement from results -->
- **Budget efficiency**: Eliminate waste from over-allocating to saturated channels while identifying under-invested opportunities
- **Make data-driven decisions**: Replace gut-feel allocation with mathematically optimal distribution based on measured conversion rates

## Who this is for

- You want an end-to-end example of **prescriptive reasoning (optimization)** with RelationalAI.
- You’re comfortable with basic Python and linear/mixed-integer optimization concepts.

## What you’ll build

- A semantic model of channels and campaigns using concepts + properties.
- A MILP allocation model with continuous spend variables and binary “active” flags per channel–campaign pair.
- A set of constraints for min/max spend, per-campaign budgets, and minimum coverage (at least one channel per campaign).
- A solver that uses the **HiGHS** backend and prints a readable allocation table.

## What’s included

- **Model + solve script**: `ad_spend_allocation.py`
- **Sample data**: `data/channels.csv`, `data/campaigns.csv`, `data/effectiveness.csv`

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools

- Python >= 3.10

## Quickstart

Follow these steps to run the template with the included sample data.
You can customize the data and model as needed after you have it running end-to-end.

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   ```

2. **Install dependencies**

   From this folder:

   ```bash
   python -m pip install .
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

   The script solves three budget scenarios.
   The allocation table for each channel-campaign pair is printed for each scenario,
   along with the total expected conversions (objective value).
   At the end, a summary table compares the objective across scenarios to show the impact of the total budget constraint:

   ```text
   Running scenario: total_budget = 35000
   Export model...
   Execute solver job...
   Extract result...
   Finished solve

     Status: OPTIMAL, Objective: 2880.0

     Spend allocation:
                           name   value
   spend_Email_Brand_Awareness  2000.0
     spend_Email_Seasonal_Sale  2000.0
   spend_Search_Product_Launch 10000.0
     spend_Search_Seasonal_Sale  8000.0
   spend_Social_Brand_Awareness  3000.0
     spend_Video_Product_Launch 10000.0

   Running scenario: total_budget = 45000
   Export model...
   Execute solver job...
   Extract result...
   Finished solve

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

   Running scenario: total_budget = 55000
   Export model...
   Execute solver job...
   Extract result...
   Finished solve

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

## Template structure

```text
.
├─ README.md
├─ pyproject.toml
├─ ad_spend_allocation.py      # main runner / entrypoint
└─ data/                       # sample input data
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

### Import libraries and configure inputs

First, the script imports the Semantics APIs (`Model`, `data`, `where`, `require`, `sum`) and configures local inputs like `DATA_DIR`:

```python
from pathlib import Path

import pandas
from pandas import read_csv

from relationalai.semantics import Model, data, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel

DATA_DIR = Path(__file__).parent / "data"

# Disable pandas inference of string types. This ensures that string columns
# in the CSVs are loaded as object dtype. This is only required when using
# relationalai versions prior to v1.0.
pandas.options.future.infer_string = False

# --------------------------------------------------
# Define the semantic model & load data
# --------------------------------------------------

# Create a Semantics model container.
model = Model("ad_spend", use_lqp=False)
```

### Define concepts and load CSV data

Next, it defines the `Channel` and `Campaign` concepts and loads `channels.csv` and `campaigns.csv` via `data(...).into(...)`:

```python
# Channel concept: marketing channel with spend bounds (and an extra ROI field
# kept to show how additional attributes can live alongside the optimization inputs).
Channel = model.Concept("Channel")
Channel.id = model.Property("{Channel} has {id:int}")
Channel.name = model.Property("{Channel} has {name:string}")
Channel.min_spend = model.Property("{Channel} has {min_spend:float}")
Channel.max_spend = model.Property("{Channel} has {max_spend:float}")
Channel.roi_coefficient = model.Property("{Channel} has {roi_coefficient:float}")

# Load channels from CSV. The `keys` argument specifies the unique identifier for
# the concept. The .into() method will create one Channel entity per row in
# the CSV, using the specified keys to ensure uniqueness. Other properties are
# populated based on the column names in the CSV matching the property declarations.
data(read_csv(DATA_DIR / "channels.csv")).into(Channel, keys=["id"])

# Campaign concept: each campaign has a total budget across all channels.
# target_conversions is loaded as an example attribute; it is not used as a
# constraint in this template.
Campaign = model.Concept("Campaign")
Campaign.id = model.Property("{Campaign} has {id:int}")
Campaign.name = model.Property("{Campaign} has {name:string}")
Campaign.budget = model.Property("{Campaign} has {budget:float}")
Campaign.target_conversions = model.Property("{Campaign} has {target_conversions:int}")

# Load campaigns from CSV data.
data(read_csv(DATA_DIR / "campaigns.csv")).into(Campaign, keys=["id"])
```

`effectiveness.csv` contains foreign keys (`channel_id`, `campaign_id`). The template resolves them into `Channel` and `Campaign` instances and creates an `Effectiveness` concept per row.

```python
# Effectiveness concept: models the conversion rate for each channel-campaign pair.
# This is the key input that links channels and campaigns and allows us to model
# the optimization problem. In a real-world scenario, this could be derived from
# historical data or A/B tests rather than loaded from a CSV.
Effectiveness = model.Concept("Effectiveness")
Effectiveness.channel = model.Property("{Effectiveness} via {channel:Channel}")
Effectiveness.campaign = model.Property("{Effectiveness} for {campaign:Campaign}")
Effectiveness.conversion_rate = model.Property("{Effectiveness} has {conversion_rate:float}")

# Load effectiveness data from CSV.
eff_data = data(read_csv(DATA_DIR / "effectiveness.csv"))

# Define Effectiveness entities by joining the CSV data with the Channel and
# Campaign concepts.
where(
    Channel.id == eff_data.channel_id,
    Campaign.id == eff_data.campaign_id
).define(
    Effectiveness.new(channel=Channel, campaign=Campaign, conversion_rate=eff_data.conversion_rate)
)
```

### Define decision variables, constraints, and objective

An `Allocation` decision concept is created for every `Effectiveness` row. The script then loops over budget scenarios, creating a fresh `SolverModel` for each.

```python
# Allocation concept: represents the decision variables for how much to spend on each
# channel-campaign pair. Each Allocation is linked to an Effectiveness entity, which
# provides the conversion rate for that channel-campaign pair. The `spend` and
# `active` properties represent the decision variables that the solver will determine.
Allocation = model.Concept("Allocation")
Allocation.effectiveness = model.Property("{Allocation} uses {effectiveness:Effectiveness}")
Allocation.spend = model.Property("{Allocation} has {spend:float}")
Allocation.active = model.Property("{Allocation} is {active:float}")

# Define Allocation entities.
model.define(Allocation.new(effectiveness=Effectiveness))

# --------------------------------------------------
# Solve with Scenario Analysis (Numeric Parameter)
# --------------------------------------------------

# Scenarios (what-if analysis)
SCENARIO_PARAM = "total_budget"
SCENARIO_VALUES = [35000, 45000, 55000]

scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    total_budget = scenario_value

    # Create fresh SolverModel for each scenario
    solver_model = SolverModel(model, "cont")

    # Variable: spend (continuous, >= 0)
    solver_model.solve_for(
        Allocation.spend,
        name=[
            "spend",
            Allocation.effectiveness.channel.name,
            Allocation.effectiveness.campaign.name,
        ],
        lower=0,
    )

    # Variable: active (binary 0/1)
    solver_model.solve_for(
        Allocation.active,
        type="bin",
        name=[
            "active",
            Allocation.effectiveness.channel.name,
            Allocation.effectiveness.campaign.name,
        ],
    )
```

Each scenario iteration adds the same structural constraints, plus a total budget constraint parameterized by the scenario value.

```python
    # Constraint: minimum spend per channel when active
    min_spend_bound = require(
        Allocation.spend >= Allocation.effectiveness.channel.min_spend * Allocation.active
    )
    solver_model.satisfy(min_spend_bound)

    # Constraint: maximum spend per channel when active
    max_spend_bound = require(
        Allocation.spend <= Allocation.effectiveness.channel.max_spend * Allocation.active
    )
    solver_model.satisfy(max_spend_bound)

    # Constraint: per-campaign budget across all channels
    campaign_spend = (
        sum(Allocation.spend)
        .where(Allocation.effectiveness.campaign == Campaign)
        .per(Campaign)
    )
    budget_limit = require(campaign_spend <= Campaign.budget)
    solver_model.satisfy(budget_limit)

    # Constraint: require at least one active channel per campaign
    campaign_channels = (
        sum(Allocation.active)
        .where(Allocation.effectiveness.campaign == Campaign)
        .per(Campaign)
    )
    min_channels = require(campaign_channels >= 1)
    solver_model.satisfy(min_channels)

    # Constraint: total budget across all campaigns (scenario parameter)
    total_budget_limit = require(sum(Allocation.spend) <= total_budget)
    solver_model.satisfy(total_budget_limit)

    # Objective: maximize total expected conversions
    total_conversions = sum(Allocation.spend * Allocation.effectiveness.conversion_rate)
    solver_model.maximize(total_conversions)
```

### Solve and print results

For each scenario, the model is solved with a time limit of 60 seconds using the HiGHS solver.
The script prints the solver status, objective value, and a table of spend allocations for channel-campaign pairs with non-trivial spend (greater than $0.001):

```python
    # Solve the model with a time limit of 60 seconds. The `Solver` class provides
    # an interface to various optimization solvers. Here we use the open-source
    # HiGHS solver, which is suitable for linear and mixed-integer problems.
    solver_backend = Solver("highs")
    solver_model.solve(solver_backend, time_limit_sec=60)

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(solver_model.termination_status),
        "objective": solver_model.objective_value,
    })
    print(f"  Status: {solver_model.termination_status}, Objective: {solver_model.objective_value}")

    # Print spend allocation from solver results
    var_df = solver_model.variable_values().to_df()
    spend_df = var_df[var_df["name"].str.startswith("spend") & (var_df["float"] > 0.001)].rename(columns={"float": "value"})
    print(f"\n  Spend allocation:")
    print(spend_df.to_string(index=False))
```

After all scenarios run, the script prints a small summary:

```python
# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for result in scenario_results:
    print(f"  {result['scenario']}: {result['status']}, obj={result['objective']}")
```

## Customize this template

Here are some ideas for how to customize and extend this template to fit your specific use case.

### Change the scenario parameters

This template includes a simple **what-if analysis** that reruns the same optimization under different company-wide budget caps.

| Parameter | Type | Values | Description |
| --- | --- | --- | --- |
| `total_budget` | numeric | `35000`, `45000`, `55000` | Total spend cap across all campaigns |

How to customize the scenarios:

- In `ad_spend_allocation.py`, edit `SCENARIO_VALUES` to the budgets you want to test.

How to interpret results:

- If increasing `total_budget` doesn’t change the objective, the total budget cap is **non-binding** (other constraints are limiting).
- If reducing `total_budget` decreases the objective, the cap is **binding** and forces spend away from higher-converting allocations.

### Use your own data

- Replace the CSVs in `data/` with your own, keeping the same column names (or update the loading logic in `ad_spend_allocation.py`).
- Ensure that `effectiveness.csv` only references valid `channel_id` and `campaign_id` values.

### Extend the model

- Add per-channel total spend limits across all campaigns.
- Add campaign conversion targets as constraints (using `Campaign.target_conversions`).
- Add diminishing returns (piecewise linear approximations) if conversion rate decreases with spend.

### Scale up and productionize

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
