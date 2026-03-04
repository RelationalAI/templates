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

# Supply Chain Transport

## What this template is for

In freight logistics, choosing between truckload (TL) and less-than-truckload (LTL) shipping modes involves a cost trade-off. TL shipments have a fixed cost per truck but offer lower per-unit rates for large volumes. LTL shipments have a piecewise cost structure that is cheaper for small volumes but expensive at scale. On top of mode selection, freight sitting in a vendor warehouse incurs inventory holding costs. The optimal strategy balances when to ship, how much to ship, and which mode to use.

This template formulates a mixed-integer program that jointly optimizes inventory holding, transport mode selection (TL vs LTL), and shipment timing for multiple freight groups. Each freight group has its own inventory window, transport window, and arrival deadline. The solver determines the cost-minimizing plan that ships all freight on time while respecting TL capacity limits and LTL piecewise cost breakpoints.

The model demonstrates several advanced techniques: multi-period inventory flow conservation, binary mode selection with big-M coupling, piecewise linear cost modeling for LTL segments, and arrival-day linking through transit times.

## Who this is for

- Supply chain planners optimizing freight consolidation and mode selection
- Logistics analysts comparing TL vs LTL cost trade-offs
- Operations researchers building multi-period transport models
- Developers learning mixed-integer programming with RelationalAI

## What you'll build

- A mixed-integer optimization model for multi-period freight transport
- Joint inventory and transport decisions across TL and LTL modes
- Piecewise linear LTL cost modeling with segment breakpoints
- Arrival day computation linked to departure day and transit time

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
s.solve_for(FreightGroup.x_inv(t, x_inv), lower=0,
    name=["x_inv", FreightGroup.name, t],
    where=[t == std.common.range(FreightGroup.inv_start_t, FreightGroup.inv_end_t + 1)])
```

**4. Add inventory flow conservation.** Inventory on day t equals inventory on day t+1 plus what is shipped out:

```python
s.satisfy(model.where(
    FreightGroup.x_inv(t, x_inv1),
    FreightGroup.x_inv(t + 1, x_inv2),
    TransportType.x_qty_tra(FreightGroup, t, x_qty_tra),
).require(x_inv1 == x_inv2 + sum(x_qty_tra).per(FreightGroup, t)))
```

**5. Minimize total cost.** The objective combines inventory holding costs, TL fixed costs, and piecewise LTL variable costs.

## Customize this template

- **Add more freight groups** by extending `freight_groups.csv` with additional rows and time windows.
- **Adjust cost parameters** by changing `inv_cost`, `tl_tra_cost`, or the LTL segment costs and limits.
- **Add more LTL segments** by defining additional `LTLSegment` instances for finer cost granularity.
- **Extend to multiple origins/destinations** by adding location concepts and routing constraints.
- **Add capacity constraints** on warehouses or transport links.

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
