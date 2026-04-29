---
title: "Synthetic Order Lifecycle"
description: "Generate synthetic banking-event traces (PLACE / MODIFY / CANCEL / FILL) that satisfy MiFID II / RegNMS-flavour sequencing rules using a CSP solver."
featured: false
experience_level: intermediate
industry: "Banking"
reasoning_types:
  - Rules-based
  - Prescriptive
tags:
  - constraint-programming
  - test-data-generation
  - banking
  - market-surveillance
---

# Synthetic Order Lifecycle

## What this template is for

Banking compliance and market-surveillance teams test their alert engines against synthetic order-event traces -- sequences of `PLACE`, `MODIFY`, `CANCEL`, and `FILL` events that real trading desks generate. Producing realistic traces by hand is hard: the events have to honour temporal precedence (a fill cannot happen before the placement), status-transition validity (no events after a cancel), venue eligibility (the symbol has to be tradable on that venue), and quantity conservation (filled shares cannot exceed the order size).

This template formulates the trace-generation problem as a constraint satisfaction model using RelationalAI's prescriptive reasoning. A pre-allocated pool of empty event slots is given to the solver; it picks each slot's type, timestamp, venue, quantity, and tick price so that every MiFID II / RegNMS-flavour rule holds. The solver (MiniZinc) returns one feasible trace that satisfies every constraint at once.

The same pattern applies to any test-data-generation problem where rows have to satisfy referential integrity, temporal precedence, and cross-row aggregate rules: claim adjudication regression suites, eligibility records, audit logs, IoT event streams.

## Who this is for

- Compliance engineers building surveillance-engine regression suites
- Bank IT teams building MiFID II / SEC Rule 613 audit-trail validators
- Software developers who need synthetic events that respect referential integrity and temporal rules
- Operations researchers learning constrained generation as a CSP problem

## What you'll build

- A constraint model with binary type indicators (`is_place`, `is_modify`, `is_cancel`, `is_fill`) and integer decision properties for `ts_ms`, `qty`, `tick_price`, `venue_id`
- Categorical regular-language transitions (`PLACE` first, nothing-after-`CANCEL`) encoded as pairwise temporal rules
- Cross-table aggregate constraint: total `FILL` quantity per order cannot exceed `Order.original_qty`
- Venue eligibility encoded as a relationship lookup against the event's chosen `venue_id`
- Post-solve verification via `problem.verify()` confirming every named constraint holds in the returned trace

## What's included

- `synthetic_order_lifecycle.py` -- main script with ontology, decisions, constraints, and solver call
- `data/symbols.csv` -- 3 tradable symbols (AAPL, MSFT, GOOG)
- `data/venues.csv` -- 3 trading venues (NYSE, NASDAQ, ARCA)
- `data/symbol_venues.csv` -- per-symbol venue eligibility
- `data/orders.csv` -- 3 orders, each with `symbol_id`, `original_qty`, and `original_tick_price` (in integer ticks of 1c)
- `data/events.csv` -- 9 pre-allocated event slots (3 per order)
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
   curl -O https://docs.relational.ai/templates/zips/v1/synthetic_order_lifecycle.zip
   unzip synthetic_order_lifecycle.zip
   cd synthetic_order_lifecycle
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
   python synthetic_order_lifecycle.py
   ```

6. Expected output (the solver returns one feasible trace; the exact event types, timestamps, and quantities will vary):
   ```text
   Generated event trace (one row per slot):
     order_id  symbol  event_id  ts_ms  is_place  is_modify  is_cancel  is_fill  qty  tick_price  venue_id
            1   AAPL         1      1         1          0          0        0  100       17500         2
            1   AAPL         2     42         0          0          0        1   60       17500         2
            1   AAPL         3     87         0          0          0        1   40       17500         2
            2   MSFT         4      1         1          0          0        0   50       35000         3
            2   MSFT         5     30         0          1          0        0    1       35000         3
            2   MSFT         6     12         0          0          0        1   25       35000         2
            3   GOOG         7      1         1          0          0        0   75       14000         2
            3   GOOG         8     50         0          0          0        1   30       14000         2
            3   GOOG         9     71         0          0          1        0    1       14000         2

   Filled quantity per order (cannot exceed Order.original_qty):
     order_id  original_qty  filled_qty
            1           100         100
            2            50          25
            3            75          30
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── synthetic_order_lifecycle.py
└── data/
    ├── symbols.csv
    ├── venues.csv
    ├── symbol_venues.csv
    ├── orders.csv
    └── events.csv
```

## How it works

**1. Define symbols, venues, orders, and a pool of event slots.** Each `OrderEvent` is a pre-allocated row tied to one `Order`; the solver decides what kind of event it is and when it happens:

```python
Order = model.Concept("Order", identify_by={"id": Integer})
Order.original_qty = model.Property(f"{Order} has {Integer:original_qty}")
Order.original_tick_price = model.Property(f"{Order} has {Integer:original_tick_price}")
Order.symbol = model.Relationship(f"{Order} is for {Symbol}")

OrderEvent = model.Concept("OrderEvent", identify_by={"event_id": Integer})
OrderEvent.order = model.Relationship(f"{OrderEvent} belongs to {Order}")
```

The `Symbol.allows(venue_id)` relationship is loaded from `symbol_venues.csv` and used later as a table-style lookup against the event's chosen venue.

**2. Declare the decision-valued properties.** Four binary indicators (one per event type) plus four bounded integers per event:

```python
OrderEvent.is_place = model.Property(f"{OrderEvent} is place if {Integer:is_place}")
OrderEvent.is_modify = model.Property(f"{OrderEvent} is modify if {Integer:is_modify}")
OrderEvent.is_cancel = model.Property(f"{OrderEvent} is cancel if {Integer:is_cancel}")
OrderEvent.is_fill = model.Property(f"{OrderEvent} is fill if {Integer:is_fill}")
OrderEvent.ts_ms = model.Property(f"{OrderEvent} occurs at {Integer:ts_ms}")
OrderEvent.venue_id = model.Property(f"{OrderEvent} on venue {Integer:venue_id}")
OrderEvent.qty = model.Property(f"{OrderEvent} has qty {Integer:qty}")
OrderEvent.tick_price = model.Property(f"{OrderEvent} has tick price {Integer:tick_price}")

problem.solve_for(OrderEvent.is_place, type="bin", name=["is_place", OrderEvent.event_id])
# ...one solve_for per binary, plus bounded solve_for for each integer.
```

The four binary indicators are constrained to sum to 1 per event, so each slot picks exactly one type.

**3. Encode the temporal regular-language rules.** Two pairwise rules over the same `OrderEvent` concept handle PLACE-first and nothing-after-CANCEL. A bounded big-M makes each rule vacuous whenever the indicator that activates it is 0:

```python
A = OrderEvent.ref()
B = OrderEvent.ref()

place_first_ic = model.where(
    A.order(Order),
    B.order(Order),
    A.event_id != B.event_id,
).require(B.ts_ms - A.ts_ms >= 1 - BIG_M_TS * (1 - A.is_place))

no_after_cancel_ic = model.where(
    A.order(Order),
    B.order(Order),
    A.event_id != B.event_id,
).require(A.ts_ms - B.ts_ms >= 1 - BIG_M_TS * (1 - A.is_cancel))
```

Read each rule as: `if A is the activating event (place / cancel), the time-ordering inequality holds; otherwise the rule is vacuously satisfied`. A `distinct_ts_ic` constraint requires every event in an order to land at its own moment.

**4. Tie PLACE events back to the order's original size and price.** Combined with a global `qty <= original_qty` bound, the big-M form pins PLACE events to the order's `original_qty`:

```python
qty_upper_ic = model.where(
    OrderEvent.order(Order),
).require(OrderEvent.qty <= Order.original_qty)

place_qty_match_ic = model.where(
    OrderEvent.order(Order),
).require(
    Order.original_qty - OrderEvent.qty <= BIG_M_QTY * (1 - OrderEvent.is_place)
)
```

**5. Constrain venue eligibility and total fill conservation.** The venue rule reads the relationship `Symbol.allows(int)` with a decision-variable argument; PyRel turns this into a table-style constraint over the event's `venue_id`. An auxiliary `fill_qty` decision is channelled to either `qty` (when `is_fill == 1`) or `0` (when `is_fill == 0`) by three big-M bounds, so the per-order conservation aggregate stays linear:

```python
venue_ok_ic = model.where(
    OrderEvent.order(Order),
    Order.symbol(Symbol),
).require(Symbol.allows(OrderEvent.venue_id))

fill_qty_le_qty_ic = model.where(...).require(OrderEvent.fill_qty <= OrderEvent.qty)
fill_qty_zero_off_ic = model.where(...).require(
    OrderEvent.fill_qty <= BIG_M_QTY * OrderEvent.is_fill
)
fill_qty_match_on_ic = model.where(...).require(
    OrderEvent.qty - OrderEvent.fill_qty <= BIG_M_QTY * (1 - OrderEvent.is_fill)
)

fill_sum_ic = model.where(
    OrderEvent.order(Order),
).require(sum(OrderEvent.fill_qty).per(Order) <= Order.original_qty)
```

**6. Solve and verify.** A single solve returns one feasible trace. After solving, `problem.verify()` fires the named constraints to confirm the trace satisfies every rule, and the termination-status gate asserts the solver reported `OPTIMAL` (MiniZinc returns `OPTIMAL` for any feasible solution under a pure satisfaction model):

```python
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()
problem.verify(
    type_sum_ic, exactly_one_place_ic, at_most_one_cancel_ic, distinct_ts_ic,
    place_first_ic, no_after_cancel_ic, qty_upper_ic, place_qty_match_ic,
    venue_ok_ic, fill_qty_le_qty_ic, fill_qty_zero_off_ic, fill_qty_match_on_ic,
    fill_sum_ic,
)
model.require(problem.termination_status() == "OPTIMAL")
```

## Customize this template

- **Use your own pool** by replacing the five CSV files with your symbols, venues, allowed (symbol, venue) pairs, orders, and event slots. The constraint structure does not change. Add more events per order to allow longer traces; the model adapts to the number of rows in `events.csv`.
- **Force a CANCEL on every order** by changing `at_most_one_cancel_ic` from `<= 1` to `== 1`, then bumping the per-order event count so the order has room for a `PLACE` plus other events before the `CANCEL`.
- **Add the inverse rule "no MODIFY after FILL"** with another pairwise big-M constraint mirroring `no_after_cancel_ic` (require `A.ts_ms - B.ts_ms >= 1 - BIG_M_TS * (1 - A.is_modify)` whenever `B` is a fill -- i.e. wedge a `B.is_fill == 1` filter into the `where` clause and keep the same indicator-style implication on the modify side).
- **Generate a "smallest violating trace" instead of a positive trace** by negating one of the rules (e.g. drop `no_after_cancel_ic` and add `model.require(sum(A.is_cancel + B.is_fill - 1).per(Order) >= 0)` plus a temporal predicate) and minimising the number of events. The model is already in optimisation-ready shape -- the termination-status gate stays at `"OPTIMAL"`.
- **Replace the synthetic time horizon** by reading `ts_ms` bounds from your real session schedule (market open / market close) and updating `TS_MIN` / `TS_MAX`.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- The pool may be too small. With three event slots per order, a `CANCEL` event consumes the only slot left after `PLACE`, so any test that demands two fills plus a cancel will fail. Add more rows to `events.csv` for that order.
- A symbol with zero allowed venues in `symbol_venues.csv` will block the `venue_ok_ic` constraint -- every event has to land on an allowed venue. Confirm at least one (symbol, venue) row exists per symbol used in `orders.csv`.
- A clash between `qty_upper_ic` and `place_qty_match_ic` shows up as INFEASIBLE if `Order.original_qty` is set higher than the `qty` upper bound derived from data. The `qty` decision domain is `[1, max(orders.original_qty)]`; raise `original_qty` consistently or rebuild the model with a larger upper bound.

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
  <summary>MiniZinc solver not available</summary>

- This template uses the MiniZinc constraint solver. Ensure the RAI Native App version supports MiniZinc.
- HiGHS is not appropriate here -- this is a discrete satisfaction model with categorical decisions, not LP/MILP.

</details>

<details>
  <summary>The generated trace differs between runs</summary>

- This is constraint satisfaction, not optimisation. Any feasible trace is a valid answer; the solver is free to return different ones across runs.
- To pin a single answer, switch to optimisation -- e.g. `problem.minimize(sum(OrderEvent.ts_ms))` returns the trace with the earliest event timestamps overall.

</details>
