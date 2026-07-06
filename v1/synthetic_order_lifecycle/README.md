---
title: "Synthetic Order Lifecycle"
description: "Generate synthetic order-lifecycle event traces (PLACE / MODIFY / CANCEL / FILL) that satisfy MiFID II / Reg NMS-flavour sequencing rules."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
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

This template formulates the trace-generation problem as a **constraint satisfaction** model using RelationalAI's **prescriptive** reasoning. A pre-allocated pool of empty event slots is given to the solver; it picks each slot's type, timestamp, venue, quantity, and tick price so that every sequencing rule holds (the rules are drawn from [ESMA RTS 24](https://www.esma.europa.eu/sites/default/files/library/2015/11/2015-esma-1464_annex_i_-_draft_rts_and_its_on_mifid_ii_and_mifir.pdf) for MiFID II and [SEC Rule 613](https://www.sec.gov/rules/final/2012/34-67457.pdf) for Reg NMS / Consolidated Audit Trail). The solver (MiniZinc) returns one feasible trace that satisfies every constraint at once.

This template constrains *type distribution and ordering*. The semantics of MODIFY (how it differs from the prior state) are not enforced -- a MODIFY event simply consumes a non-PLACE / non-CANCEL / non-FILL slot. See "Customize this template" below for how to add MODIFY-meaningful constraints (e.g. forbidding `MODIFY` after `FILL`, or pinning a `tick_price`/`qty` delta).

The same pattern applies to any test-data-generation problem where rows have to satisfy referential integrity, temporal precedence, and cross-row aggregate rules: claim adjudication regression suites, eligibility records, audit logs, IoT event streams.

## Who this is for

- Compliance engineers building surveillance-engine regression suites
- Bank IT teams building MiFID II / SEC Rule 613 audit-trail validators
- Software developers who need synthetic events that respect referential integrity and temporal rules
- Operations researchers learning constrained generation as a CSP problem

## What you'll build

- A constraint model with an `EventType` enum (`PLACE`, `MODIFY`, `CANCEL`, `FILL`) indexing one binary type indicator per (event slot, type), plus integer decision properties for `ts_ms`, `qty`, `tick_price`, `venue_id`
- Categorical regular-language transitions (`PLACE` first, nothing-after-`CANCEL`) encoded as pairwise temporal rules
- Cross-table aggregate constraint: total `FILL` quantity per order cannot exceed `Order.original_qty`
- An auxiliary `fill_qty` decision channeled to `qty` when the `FILL` indicator is 1 (else 0) via two `implies` so the per-order fill-conservation aggregate stays linear
- Value-pinning: PLACE event's `qty` and `tick_price` pinned to the order's `original_qty` and `original_tick_price` via `implies`
- Venue eligibility encoded as a relationship lookup against the event's chosen `venue_id`
- Post-solve verification via `problem.verify()` confirming every re-evaluable constraint in the returned trace (`implies`-bodied and `all_different`-bodied ICs are solver-side only and intentionally excluded -- see step 5)

## What's included

- `synthetic_order_lifecycle.py` -- main script with ontology, decisions, constraints, and solver call
- `data/symbols.csv` -- 5 tradable symbols (AAPL, MSFT, GOOG, NVDA, TSLA)
- `data/venues.csv` -- 5 trading venues (NYSE, NASDAQ, ARCA, BATS, IEX)
- `data/symbol_venues.csv` -- 13 (symbol, venue) eligible pairs out of 25 possible (sparser than full coverage so venue eligibility visibly binds)
- `data/orders.csv` -- 6 orders, each with `symbol_id`, `original_qty`, and `original_tick_price` (in integer ticks of 1c, so `17500` reads as $175.00)
- `data/events.csv` -- 36 pre-allocated event slots (6 per order)
- `pyproject.toml` -- Python package configuration

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- A Snowflake user with permissions to access the RAI Native App.

### Tools
- Python >= 3.10
- RelationalAI Python SDK (`relationalai == 1.13.0`)

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

4. Configure (prompts for Snowflake account, role, and profile name):
   ```bash
   rai init
   ```

5. Run:
   ```bash
   python synthetic_order_lifecycle.py
   ```

6. Expected output. The script prints the formulation (every variable and constraint, ~1,000 lines on the sample data, omitted here; each event's four type indicators all print as `is_type_<event id>` -- so `is_type_1` appears four times -- because variable names are keyed by event id), the solve-result block, the full event trace (all 36 rows; abridged below to the first AAPL block), and per-order fill totals. Rows are sorted by `(order_id, ts_ms)`; the `type` column reads each event's chosen `EventType` member name back from a derived enum-typed property (`OrderEvent.event_type.name`), with no display-side post-processing. Exact event types, timestamps, quantities, prices, and venues vary across runs and solver versions:
   ```text
   Solve result:
   • status: OPTIMAL
   • solve time: 1.17s
   • num_points: 1
   • solver: MiniZinc_unknown
   • raw status string: SATISFIABLE

   Generated event trace (one row per slot, sorted by order then timestamp):
    order_id symbol  event_id  ts_ms   type  qty  tick_price venue
           1   AAPL         4    995  PLACE  100       17500  ARCA
           1   AAPL         2    996 MODIFY  100       17501  ARCA
           1   AAPL         3    997 MODIFY  100       17501  ARCA
           1   AAPL         6    998   FILL  100       17501  ARCA
           1   AAPL         5    999 MODIFY  100       17501  ARCA
           1   AAPL         1   1000 MODIFY  100       17501  ARCA
    ...    [rows for orders 2-6 omitted for brevity; the script prints all 36 rows -- 6 events per order across orders 1-6]

   Filled quantity per order (cannot exceed Order.original_qty):
      order_id original_qty filled_qty
   0         1          100        100
   1         2           50         50
   2         3           80         80
   3         4          200        200
   4         5          120        117
   5         6           60         60
   ```

   The AAPL block above is one of six orders; the others follow the same shape. PLACE has the smallest `ts_ms` per order with `qty` / `tick_price` pinned to the order row, and venues are constrained to the symbol's eligible set (here `{NYSE, NASDAQ, ARCA}` for AAPL). The conservation IC is `sum(fill_qty) <= original_qty`; the run above fills exactly `original_qty` on five orders and 117 of 120 on order 5 -- any fill total at or below the original quantity is a valid trace.

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

The solver decides every event's type, timestamp, venue, and quantity. The script proceeds in five steps.

**1. Define the ontology and load data.** `Symbol`, `Venue`, `Order`, and `OrderEvent` concepts are declared with their identifying properties; `SymbolVenue` and a derived `NotAllowedSymbolVenue` capture the eligible (and dual disallowed) symbol/venue pairs. CSV rows from `data/` populate every concept and relationship. `NotAllowedSymbolVenue` is an encoding artifact, not a domain concept: the CSP arithmetic supports only `!=, *, +, -`, so the rule is encoded as "forbid these pairs" rather than the more natural "require an allowed pair".

**2. Declare decision variables.** The event-type vocabulary is a `model.Enum` (`EventType`: `PLACE`, `MODIFY`, `CANCEL`, `FILL`), and a single enum-indexed property `OrderEvent.has_type` carries one binary indicator per (event slot, type), declared with a single `solve_for` call. Each slot also gets integer decisions (`ts_ms`, `qty`, `tick_price`, `venue_id`). An auxiliary `fill_qty` decision channels `qty` when the `FILL` indicator is 1 (else 0) so the per-order fill-conservation aggregate stays linear:

```python
class EventType(model.Enum):
    PLACE = 1
    MODIFY = 2
    CANCEL = 3
    FILL = 4

OrderEvent.has_type = model.Property(
    f"{OrderEvent} is {EventType:event_type} if {Integer:indicator}"
)
problem.solve_for(OrderEvent.has_type, type="bin", name=["is_type", OrderEvent.event_id])
```

Constraints slice the indicators by member: a `where` clause like `OrderEvent.has_type(EventType.PLACE, place_ind)` binds `place_ind` to each event's `PLACE` indicator, which the constraint body then aggregates or gates on.

**3. Add sequencing rules as pairwise temporal constraints.** Conditional rules read as 'if premise then consequent'. PLACE-first and nothing-after-CANCEL are pairwise rules over two refs into the same concept; `A.order == B.order` asserts same-order without a free `Order` variable:

```python
A = OrderEvent.ref()
B = OrderEvent.ref()

a_place_ind = Integer.ref()
place_first_ic = model.where(
    A.order == B.order,
    A.event_id != B.event_id,
    A.has_type(EventType.PLACE, a_place_ind),
).require(implies(a_place_ind == 1, A.ts_ms < B.ts_ms))
```

Distinctness within a group is one global constraint, not pairwise `!=`. `all_different.per(...)` lowers to MiniZinc's native alldifferent propagator:

```python
distinct_ts_ic = model.require(all_different(OrderEvent.ts_ms).per(OrderEvent.order))
```

**4. Walk relationships in line for cross-table rules.** Reading the order's `original_qty` from an event, or matching disallowed venue pairs through the order's symbol -- no intermediate refs needed:

```python
qty_upper_ic = model.require(OrderEvent.qty <= OrderEvent.order.original_qty)

venue_ok_ic = model.where(
    OrderEvent.order.symbol.id(NotAllowedSymbolVenue.symbol_id),
).require(NotAllowedSymbolVenue.venue_id != OrderEvent.venue_id)
```

Value-pinning couples a decision variable to a data property via `implies`. The PLACE event's `qty` and `tick_price` are pinned to the order's `original_qty` and `original_tick_price` so the generated trace stays internally consistent with the order's stated price and size:

```python
place_qty_ind = Integer.ref()
place_qty_match_ic = model.where(OrderEvent.has_type(EventType.PLACE, place_qty_ind)).require(
    implies(place_qty_ind == 1, OrderEvent.qty == OrderEvent.order.original_qty)
)
place_price_ind = Integer.ref()
place_price_match_ic = model.where(OrderEvent.has_type(EventType.PLACE, place_price_ind)).require(
    implies(
        place_price_ind == 1,
        OrderEvent.tick_price == OrderEvent.order.original_tick_price,
    )
)
```

**5. Solve and verify.** `implies` and `all_different` are solver-only. They go to `satisfy()` but must NOT be passed to `verify()` -- the relational engine cannot re-evaluate wire-format constraint relations and would return silently-OK regardless of whether the constraint actually holds. The remaining ICs are plain relational arithmetic and ARE re-evaluated by `verify()`:

```python
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

problem.verify(
    type_sum_ic,
    exactly_one_place_ic,
    at_most_one_cancel_ic,
    qty_upper_ic,
    venue_ok_ic,
    fill_sum_ic,
)
model.require(problem.termination_status() == "OPTIMAL")
```

## Customize this template

- **Use your own pool** by replacing the five CSV files with your symbols, venues, allowed (symbol, venue) pairs, orders, and event slots. The constraint structure does not change. Add more events per order to allow longer traces; the model adapts to the number of rows in `events.csv`. Two assumptions on your data:
  - `venues.csv` ids should be contiguous `1..N` -- the `venue_id` decision domain is `[1, max(venue_id)]`, so non-contiguous ids would let the solver pick venue ids that don't exist.
  - At least one disallowed `(symbol, venue)` pair must exist -- if your `symbol_venues.csv` covers every symbol×venue combination, the empty disallowed list breaks `model.data(...).to_schema()`. In that case drop `venue_ok_ic`.
- **Force a CANCEL on every order** by changing `at_most_one_cancel_ic` from `<= 1` to `== 1`, then bumping the per-order event count so the order has room for a `PLACE` plus other events before the `CANCEL`.
- **Add the inverse rule "no MODIFY after FILL"** with the same shape as `place_first_ic`, but filtering `B` to fills. `A` and `B` are the two `OrderEvent.ref()` aliases declared earlier in the script alongside `place_first_ic`:
  ```python
  # A = OrderEvent.ref(); B = OrderEvent.ref()  # already declared earlier
  a_modify_ind = Integer.ref()
  b_fill_ind = Integer.ref()
  no_modify_after_fill_ic = model.where(
      A.order == B.order,
      A.event_id != B.event_id,
      A.has_type(EventType.MODIFY, a_modify_ind),
      B.has_type(EventType.FILL, b_fill_ind),
      b_fill_ind == 1,
  ).require(implies(a_modify_ind == 1, A.ts_ms < B.ts_ms))
  ```
- **Generate a "smallest violating trace" instead of a positive trace** by negating one of the rules (e.g. drop `no_after_cancel_ic`, bind `A`'s `CANCEL` and `B`'s `FILL` indicators via `has_type` in a `where`, and add `model.require(sum(a_cancel_ind + b_fill_ind - 1).per(Order) >= 0)` plus a temporal predicate) and minimizing the number of events. The model is already in optimization-ready shape -- the termination-status gate stays at `"OPTIMAL"`.
- **Replace the synthetic time horizon** by reading `ts_ms` bounds from your real session schedule (market open / market close) and updating `TS_MIN` / `TS_MAX`.

## Troubleshooting

<details>
  <summary>Import error or AttributeError on <code>relationalai</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`. The pinned version (`relationalai==1.13.0`) ships enum members as constants across the DSL and prescriptive reasoning (alongside the `solve_info()`, `verify()`, and chained-`where().require()` APIs); older versions reject the enum-indexed decision variable and produce type or attribute errors.
- If you share a venv across templates, run `python -m pip install --upgrade --force-reinstall relationalai==1.13.0`.

</details>

<details>
  <summary>FileNotFoundError on a CSV</summary>

- The script resolves data paths as `Path(__file__).parent / "data"`. Run `python synthetic_order_lifecycle.py` from the unzipped template root, not from a parent directory.
- Confirm `data/` contains `symbols.csv`, `venues.csv`, `symbol_venues.csv`, `orders.csv`, and `events.csv`.

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
  <summary>Solver returns INFEASIBLE</summary>

- The pool may be too small. If you reduce `events.csv` below the per-order slot count required by your constraints (e.g. one `PLACE` plus a forced `CANCEL` with no room for fills), no trace can satisfy all the rules. Add more rows to `events.csv` for that order.
- A symbol with zero allowed venues in `symbol_venues.csv` will block the `venue_ok_ic` constraint -- every event has to land on an allowed venue. Confirm at least one (symbol, venue) row exists per symbol used in `orders.csv`.
- Every order in `orders.csv` must have `original_qty >= 1` and `original_tick_price >= 1`. The `qty` and `tick_price` decision domains start at `1`, and the PLACE-event pinning ICs equate them to the order's stated values; a row with zero in either column produces an empty domain and immediate INFEASIBLE.

</details>

<details>
  <summary>Empty disallowed pairs (full venue coverage)</summary>

- If you replace `symbol_venues.csv` with a list that covers every (symbol, venue) combination, the derived `disallowed_csv` is empty and `model.data(...).to_schema()` raises `ValueError: empty data` (or a similar zero-row schema error from pandas). Drop the `venue_ok_ic` constraint when full coverage is intentional.

</details>

<details>
  <summary>The generated trace differs between runs</summary>

- This is constraint satisfaction, not optimization. Any feasible trace is a valid answer; the solver is free to return different ones across runs.
- To pin a single answer, switch to optimization -- e.g. `problem.minimize(sum(OrderEvent.ts_ms))` returns the trace with the earliest event timestamps overall.

</details>
