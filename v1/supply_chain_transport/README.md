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

- `supply_chain_transport.py` -- main script with ontology, formulation, and solver call
- `data/freight_groups.csv` -- 2 freight groups with inventory/transport/arrival windows
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai` == 1.0.14)

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/supply_chain_transport.zip
   unzip supply_chain_transport.zip
   cd supply_chain_transport
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
   python supply_chain_transport.py
   ```

6. Expected output:
   ```text
   Status: OPTIMAL
   Total cost: $5080.00

   === Inventory Levels ===
   freight_group  day  inventory
             fg1    1     4000.0
             fg1    2     4000.0
             fg1    3        0.0
             fg1    4        0.0
             fg2    2     5000.0
             fg2    3     5000.0
             fg2    4        0.0
             fg2    5        0.0

   === Transport Quantities ===
   type freight_group  day  quantity
     tl           fg1    2    4000.0
     tl           fg2    3    5000.0

   === Arrival Days ===
   freight_group  arrival_day
             fg1          4.0
             fg2          5.0
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── supply_chain_transport.py
└── data/
    └── freight_groups.csv
```

**Start here**: run `python supply_chain_transport.py` for the full formulation and solve end to end.

## Sample data

The bundled data is synthetic and illustrative -- a minimal two-group example designed to teach the formulation on a Snowflake-connected RAI account, not to match a specific shipper's freight book. The transport modes and cost segments are defined inline in the script, not loaded from CSV.

- **`freight_groups.csv`** (2 rows) -- one row per freight group, giving its inventory window (`inv_start_t` to `inv_end_t`), transport window (`tra_start_t` to `tra_end_t`), arrival window (`arr_start_t` to `arr_end_t`), and starting inventory weight (`inv_start`).

## Model overview

The formulation is built on three concepts: the freight groups loaded from CSV, and the transport types and LTL cost segments defined inline in the script.

- **Key entities**: `FreightGroup`, `TransportType`, `LTLSegment`.
- **Primary identifiers**: `name` on `FreightGroup` and `TransportType`; integer `seg` on `LTLSegment`.
- **Important invariants**: window start days are less than or equal to window end days; `inv_start` weights are non-negative; transport-mode indicators and segment activation variables are binary; each freight group ships all inventory out by the end of its inventory window.

### Concepts

**`FreightGroup`** -- a batch of freight with its own inventory, transport, and arrival time windows. The optimization solves for its per-day inventory, shipment quantities, and arrival day.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `name` | String | Yes | Loaded from `data/freight_groups.csv` |
| `inv_start_t`, `inv_end_t` | Integer | No | Inventory window (first/last day) |
| `tra_start_t`, `tra_end_t` | Integer | No | Transport (departure) window |
| `arr_start_t`, `arr_end_t` | Integer | No | Arrival deadline window |
| `inv_start` | Float | No | Starting inventory weight |
| `x_inv` | Float | No | Decision: inventory level per day |
| `z_arr_day` | Float | No | Decision: computed arrival day |

**`TransportType`** -- a shipping mode (truckload or less-than-truckload), defined inline with its transit time.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `name` | String | Yes | `tl` or `ltl` |
| `transit_time` | Integer | No | Days in transit (TL = 2, LTL = 3) |
| `x_qty_tra` | Float | No | Decision: quantity shipped per group per day |
| `y_bin_tra` | Float | No | Decision: binary mode indicator |
| `x_weight` | Float | No | Decision: total weight shipped per departure day |

**`LTLSegment`** -- a breakpoint in the piecewise-linear less-than-truckload cost curve, defined inline.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `seg` | Integer | Yes | Segment index |
| `limit` | Float | No | Upper weight bound for the segment |
| `cost` | Float | No | Per-unit cost within the segment |
| `x_rem_ltl` | Float | No | Decision: weight routed through this segment per day |
| `y_bin_ltl` | Float | No | Decision: binary segment-activation indicator |

## How it works

**1. Define freight groups with time windows.** Each freight group has inventory, transport, and arrival windows loaded from CSV:

```python
FreightGroup = Concept("FreightGroup", identify_by={"name": String})
FreightGroup.inv_start_t = Property(f"{FreightGroup} has {Integer:inv_start_t}")
FreightGroup.tra_start_t = Property(f"{FreightGroup} has {Integer:tra_start_t}")
FreightGroup.inv_start = Property(f"{FreightGroup} has {Float:inv_start}")
```

**2. Define transport types and LTL cost segments.** TL and LTL modes are defined inline with transit times. LTL uses a piecewise linear cost structure:

```python
tl = TransportType.new(name="tl")
ltl = TransportType.new(name="ltl")
model.define(tl, tl.transit_time(2))
model.define(ltl, ltl.transit_time(3))

seg1 = LTLSegment.new(seg=1)
model.define(seg1, seg1.limit(6000.0), seg1.cost(0.18))
```

**3. Formulate decision variables.** The model solves for inventory levels, transport quantities, binary mode indicators, arrival days, and piecewise LTL segment variables:

```python
problem.solve_for(FreightGroup.x_inv(time_period_ref, x_inv), lower=0,
    name=["x_inv", FreightGroup.name, time_period_ref],
    where=[time_period_ref == std.common.range(FreightGroup.inv_start_t, FreightGroup.inv_end_t + 1)])
```

**4. Add inventory flow conservation.** Inventory on day t equals inventory on day t+1 plus what is shipped out:

```python
problem.satisfy(model.where(
    FreightGroup.x_inv(time_period_ref, x_inv_current),
    FreightGroup.x_inv(time_period_ref + 1, x_inv_next),
    TransportType.x_qty_tra(FreightGroup, time_period_ref, x_qty_tra),
).require(x_inv_current == x_inv_next + sum(x_qty_tra).per(FreightGroup, time_period_ref)))
```

**5. Minimize total cost.** The objective combines inventory holding costs, TL fixed costs, and piecewise LTL variable costs.

## Customize this template

Focus on the first changes most users will make.

### Use your own data

- Replace `data/freight_groups.csv` with your own; keep the column names listed in *Sample data* above.
- Ensure each group's windows are internally consistent (start day less than or equal to end day) and that the arrival window is reachable given transit times.

### Tune parameters

- **Cost parameters** -- change `inv_cost`, `tl_tra_cost`, or the LTL segment costs and limits in the script.
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

- Run `rai init` to create or update your RelationalAI/Snowflake configuration.
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
