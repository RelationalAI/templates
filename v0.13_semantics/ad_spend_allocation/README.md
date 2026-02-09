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

- **Improve ROAS**: Achieve higher Return on Ad Spend compared to manual allocation or simple rules <!-- TODO: Add % improvement from results -->
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
- **Outputs**: prints solver status, objective value, and a spend allocation table

## Prerequisites

### Access

- RelationalAI account with access to a Snowflake account that has the RAI Native App installed.

### Tools

- Python >= 3.10
- Python packages: `relationalai==0.13.3`, `pandas` (see `pyproject.toml`)
- Optional: the `rai` CLI (installed with the `relationalai` Python package)

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

   The script prints a termination status, the objective value (total expected conversions), and a table of non-zero spend decisions, for example:

   ```text
   Status: OPTIMAL
   Total expected conversions: 3430

   Spend allocation:
   channel        campaign  active?   spend
     Email Brand_Awareness      1.0  2000.0
     Email   Seasonal_Sale      1.0  2000.0
    Search Brand_Awareness      1.0  5000.0
    Search  Product_Launch      1.0 10000.0
    Search   Seasonal_Sale      1.0  8000.0
    Social Brand_Awareness      1.0  8000.0
     Video  Product_Launch      1.0 10000.0
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

### 1) Read CSVs with RAI-compatible dtypes

```python
from pandas import read_csv as pd_read_csv

def read_csv(path):
  """Read CSV with RAI-compatible dtypes.

  Pandas may use StringDtype for string columns, but RAI's data().into()
  requires object dtype. This function ensures compatibility.
  """
  df = pd_read_csv(path)
  # Convert StringDtype to object for RAI compatibility
  string_cols = df.select_dtypes("string").columns
  if len(string_cols) > 0:
    df = df.astype({col: "object" for col in string_cols})
  return df
```

### 2) Create a model and load inputs

The template builds a Semantics `Model`, defines concepts + properties, and loads CSVs into those concepts.

```python
model = Model("ad_spend", use_lqp=False)

# `Channel`: marketing channel with spend bounds (and an extra ROI field kept to
# show how additional attributes can live alongside the optimization inputs).
Channel = model.Concept("Channel")
Channel.id = model.Property("{Channel} has {id:int}")
Channel.name = model.Property("{Channel} has {name:string}")
Channel.min_spend = model.Property("{Channel} has {min_spend:float}")
Channel.max_spend = model.Property("{Channel} has {max_spend:float}")
Channel.roi_coefficient = model.Property("{Channel} has {roi_coefficient:float}")
data(read_csv(DATA_DIR / "channels.csv")).into(Channel, keys=["id"])

# `Campaign`: each campaign has a total budget across all channels.
# `target_conversions` is loaded as an example attribute; it is not used as a
# constraint in this template.
Campaign = model.Concept("Campaign")
Campaign.id = model.Property("{Campaign} has {id:int}")
Campaign.name = model.Property("{Campaign} has {name:string}")
Campaign.budget = model.Property("{Campaign} has {budget:float}")
Campaign.target_conversions = model.Property("{Campaign} has {target_conversions:int}")
data(read_csv(DATA_DIR / "campaigns.csv")).into(Campaign, keys=["id"])
```

### 2) Build channel–campaign effectiveness rows

`effectiveness.csv` contains foreign keys (`channel_id`, `campaign_id`). The template resolves them into `Channel` and `Campaign` instances and creates an `Effectiveness` concept per row.

```python
# `Effectiveness`: one row per (channel, campaign) with an expected conversion rate.
Effectiveness = model.Concept("Effectiveness")
Effectiveness.channel = model.Property("{Effectiveness} via {channel:Channel}")
Effectiveness.campaign = model.Property("{Effectiveness} for {campaign:Campaign}")
Effectiveness.conversion_rate = model.Property("{Effectiveness} has {conversion_rate:float}")

eff_data = data(read_csv(DATA_DIR / "effectiveness.csv"))
where(
    Channel.id == eff_data.channel_id,
    Campaign.id == eff_data.campaign_id
).define(
    # Create one `Effectiveness` instance per CSV row, resolving the foreign keys
    # into actual `Channel` and `Campaign` concept instances.
    Effectiveness.new(channel=Channel, campaign=Campaign, conversion_rate=eff_data.conversion_rate)
)
```

### 3) Define decision variables (MILP)

An `Allocation` decision concept is created for every `Effectiveness` row. The optimization reasoner then “solves for” two properties.

```python
# `Allocation`: decision concept (one allocation per effectiveness row).
Allocation = model.Concept("Allocation")
Allocation.effectiveness = model.Property("{Allocation} uses {effectiveness:Effectiveness}")
Allocation.spend = model.Property("{Allocation} has {spend:float}")
Allocation.active = model.Property("{Allocation} is {active:float}")
model.define(Allocation.new(effectiveness=Effectiveness))

solver_model = SolverModel(model, "cont")

# Decision variables.
# The `name=[...]` metadata is used to label variables in solver model. These show up if you print the solver model
# and are helpful for debugging.

# `spend` is continuous with a lower bound of 0.
solver_model.solve_for(
    Allocation.spend,
    name=["spend", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name],
    lower=0
)

# `active` is a binary variable (0 or 1) that indicates whether the channel–campaign pair is active.
solver_model.solve_for(
    Allocation.active,
    type="bin",
    name=["active", Allocation.effectiveness.channel.name, Allocation.effectiveness.campaign.name]
)
```

### 4) Add constraints

The template encodes spend bounds, a per-campaign budget, and a minimum coverage rule.

```python
# Constraint: spend bounded by per-channel min/max *only when active*.
# If `active = 0`, both bounds force `spend = 0`.
min_spend_bound = require(Allocation.spend >= Allocation.effectiveness.channel.min_spend * Allocation.active)
solver_model.satisfy(min_spend_bound)

max_spend_bound = require(Allocation.spend <= Allocation.effectiveness.channel.max_spend * Allocation.active)
solver_model.satisfy(max_spend_bound)

# Constraint: per-campaign budget across all channels.
campaign_spend = sum(Allocation.spend).where(Allocation.effectiveness.campaign == Campaign).per(Campaign)
budget_limit = require(campaign_spend <= Campaign.budget)
solver_model.satisfy(budget_limit)

# Constraint: require at least one active channel per campaign.
campaign_channels = sum(Allocation.active).where(Allocation.effectiveness.campaign == Campaign).per(Campaign)
min_channels = require(campaign_channels >= 1)
solver_model.satisfy(min_channels)
```

### 5) Maximize conversions, solve, and print a compact solution

The objective is linear in spend: maximize total expected conversions $= \sum spend \cdot conversion\_rate$.

```python
total_conversions = sum(Allocation.spend * Allocation.effectiveness.conversion_rate)
solver_model.maximize(total_conversions)

solver_backend = Solver("highs")
solver_model.solve(solver_backend, time_limit_sec=60)

print(f"Status: {solver_model.termination_status}")
print(f"Total expected conversions: {solver_model.objective_value:.0f}")
```

The final table is produced by querying the solved properties and filtering out near-zero spend allocations.

```python
allocations = select(
    Allocation.effectiveness.channel.name.alias("channel"),
    Allocation.effectiveness.campaign.name.alias("campaign"),
    Allocation.active.alias("active?"),
    Allocation.spend
).where(
    # Hide zero allocations to keep the output compact.
    Allocation.spend > 0.001
).to_df()

print(allocations.to_string(index=False))
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

### Scale up / productionize (optional)

- Replace CSV ingestion with Snowflake sources (see the overview in `../README.md`).
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


- Check that each campaign budget is high enough to pay for at least one active channel’s `min_spend`.
- Check that channel `min_spend` values are not greater than `max_spend`.
- Confirm conversion rates are present for each campaign (missing effectiveness rows reduce options).

</details>

<details>
  <summary>Why is the spend allocation empty?</summary>


- The script filters allocations with `Allocation.spend > 0.001`. If everything is near zero, inspect constraints and budgets.
- Confirm input CSVs were read correctly and contain rows.

</details>

---

## Next steps

- Add scenario parameters (e.g., channel saturation, campaign priorities) and compare solutions.
- Persist the results (CSV or Snowflake table) and build a small dashboard.
- Extend the objective (e.g., weighted conversions, CAC/ROAS trade-offs).
