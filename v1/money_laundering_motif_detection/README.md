---
title: "Money-Laundering Motif Detection"
description: "Enumerate every layering 'butterfly' pattern in a transaction graph using a CSP solver in multi-solution mode: a source routing under-threshold amounts through K beneficial-owner-clustered hubs to a single destination, with per-hub flow conservation in dollar amounts."
featured: false
experience_level: intermediate
industry: "Banking"
reasoning_types:
  - Graph
  - Rules-based
  - Prescriptive
tags:
  - constraint-programming
  - graph-pattern-matching
  - multi-solution
  - banking
  - financial-crime
---

# Money-Laundering Motif Detection

## What this template is for

Banking compliance and financial-crime teams hunt for "layering" -- a money-laundering pattern where a launderer routes funds from one source account through a cluster of intermediary accounts to a single destination, splitting each leg under the [FinCEN currency-transaction-report threshold](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1010/subpart-C/section-1010.311) of $10,000 so no transaction triggers a CTR filing. The intermediaries -- "hubs" -- share a beneficial owner: a single human or shell entity behind multiple accounts, who absorbs a small fee at each hop and forwards the rest. The signal is structural and arithmetic: K hubs receive from the source and forward to a destination, where each hub's incoming dollar amount equals its outgoing amount within a tight tolerance.

AML triage is plural by definition. An analyst opening their queue wants to see *every* layering pattern in the ledger -- not the first one a solver happened to enumerate. This template encodes the layering motif as a constraint satisfaction model and runs the solver in multi-solution mode: pass `solution_limit=K` to `problem.solve(...)`, then enumerate each candidate motif via `Variable.values(solution_index, value)`. The output is one row per motif edge per solution, ready to drop straight into a case-management view. The solver returns up to K *distinct* feasible motifs; ordering is not a ranking -- to rank by laundered dollars or scheme severity, swap to an objective and a one-at-a-time enumeration loop, or sort the enumerated motifs in post-processing.

The model decides which transactions are part of each motif and which accounts play which role (`is_source`, `is_hub`, `is_dest`); per-account flow conservation in count couples edge-selection to role-assignment, while per-hub flow conservation in *dollar amounts* pulls the model beyond pure pattern-matching -- the solver must balance the chosen edges' values against each other, which is the CSP arithmetic that a graph-pattern / paths library cannot express.

The same pattern applies to other graph motif-detection problems where the signal is "K accounts in the same cluster forming a fixed shape with arithmetic balance across decision-selected edges": collusion rings in marketplace fraud, ration-card sharing in welfare fraud, recurring-billing abuse with fee splitting in subscription services. In every case, the analyst wants the full population of candidates, not a single representative.

## Who this is for

- Bank financial-crime / AML compliance teams investigating layering patterns
- Fintech risk engineers building structuring-detection alert pipelines
- Bank IT teams building investigative tools that surface candidate cases for human review
- Operations researchers learning subgraph motif enumeration with flow conservation as a CSP problem

## What you'll build

- A constraint model with four binary decision streams: `Transaction.is_motif` (which transactions are part of the motif) and `Account.is_source` / `Account.is_hub` / `Account.is_dest` (which accounts play which role)
- A role-eligibility pre-pass that forces the role bits to 0 on accounts that have no outgoing transactions (cannot be source or hub) or no incoming transactions (cannot be hub or destination), so the per-account flow ICs bind correctly even on customized ledgers with isolated accounts
- Per-account flow conservation in *count* over the directed transaction graph (source has out-degree K, each hub has in-degree 1 and out-degree 1, destination has in-degree K)
- Per-hub flow conservation in *dollar amount*: each hub forwards what it receives, within `CONSERVATION_TOLERANCE_DOLLARS`. Written with `implies` so the constraint activates only on accounts the solver picks as hubs -- no big-M coefficient. Per-hub residuals are visible in the motif-transactions inspection table; an analyst can confirm per hub that `sum(motif inflow) - sum(motif outflow)` is within tolerance.
- Filter-style threshold and same-beneficial-owner predicates encoded as `where`-filtered linear constraints
- Transaction timestamps (`ts_minutes`) are loaded and printed for analyst review but are **not** part of the constraint set -- the model is a structural motif detector. Add a temporal-ordering IC in the customization section if your scheme requires hubs to receive before they forward.
- **Multi-solution enumeration as the primary code path**: `problem.solve(..., solution_limit=MAX_MOTIFS)` runs the search in enumeration mode; `Variable.values(solution_index, value)` then surfaces every candidate motif so an analyst can review them as a batch
- Post-solve sanity check via `problem.verify()` re-evaluating the pure-arithmetic ICs against the first returned solution (the implies-bodied conservation ICs are solver-only and omitted). `verify()` checks the first solution only; rely on the model itself, not `verify()`, to enforce the constraint across every motif.

## What's included

- `money_laundering_motif_detection.py` -- main script with ontology, decisions, constraints, and solver call
- `data/accounts.csv` -- 40 accounts spanning ~15 beneficial-owner clusters, including two viable hub clusters (bo=100, bo=200) and several alt-hub candidates that match by ownership but fail conservation
- `data/transactions.csv` -- 60 directed transactions: two complete butterflies (against different destinations and in different bo clusters) plus a mix of decoys -- alt-cluster paths that fail conservation, over-threshold transactions, mismatched-owner pairs, wrong-direction edges, and unrelated cross-cluster traffic
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
   curl -O https://docs.relational.ai/templates/zips/v1/money_laundering_motif_detection.zip
   unzip money_laundering_motif_detection.zip
   cd money_laundering_motif_detection
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
   python money_laundering_motif_detection.py
   ```

6. Expected output. The bundled dataset contains two complete butterflies (cluster `100` against `WireRecipientCorp`, cluster `200` against `OffshoreLLC`) plus a mix of decoys; with `solution_limit=10` the solver enumerates both and the inspect blocks tag each row with its `solution` index. Solver build strings and exact wall times will vary; the structure of the output is stable:
   ```text
   Solve result:
   • status: OPTIMAL
   • objective: 0
   • solve time: 0.53s
   • num_points: 2
   • solver: MiniZinc_nothing

   Candidate motif transactions (one row per motif edge per solution):
       solution  tx_id  src_account_id         src_name  dst_account_id           dst_name  amount  ts_min
   0          0      1               1  SourceShellCorp               2           HubAccA1    9000       5
   1          0      2               1  SourceShellCorp               3           HubAccA2    8500       7
   2          0      3               1  SourceShellCorp               4           HubAccA3    9500       9
   3          0      4               2         HubAccA1               5  WireRecipientCorp    8980      15
   4          0      5               3         HubAccA2               5  WireRecipientCorp    8475      17
   5          0      6               4         HubAccA3               5  WireRecipientCorp    9420      19
   6          1      7               6  SecondShellCorp               7           HubAccB1    7000      30
   7          1      8               6  SecondShellCorp               8           HubAccB2    7500      32
   8          1      9               6  SecondShellCorp               9           HubAccB3    7800      34
   9          1     10               7         HubAccB1              10        OffshoreLLC    6950      40
   10         1     11               8         HubAccB2              10        OffshoreLLC    7480      42
   11         1     12               9         HubAccB3              10        OffshoreLLC    7780      44

   Candidate motif hubs per solution (with shared beneficial owner):
      solution  hub_id  hub_name  bo_id
   0         0       2  HubAccA1    100
   1         0       3  HubAccA2    100
   2         0       4  HubAccA3    100
   3         1       7  HubAccB1    200
   4         1       8  HubAccB2    200
   5         1       9  HubAccB3    200

   Candidate motif source and destination per solution:
      solution  source_id      source_name  dest_id          dest_name
   0         0          1  SourceShellCorp        5  WireRecipientCorp
   1         1          6  SecondShellCorp       10        OffshoreLLC
   ```

   Each solution row is one full butterfly: a source routing three under-threshold deposits through three same-beneficial-owner hubs to a single destination, each hub absorbing a small "fee" within `CONSERVATION_TOLERANCE_DOLLARS` ($100) before forwarding the balance. The dataset's near-misses make the constraints visibly do work: alt-cluster-100 candidates `AltCluster100A` and `AltCluster100B` (bo `100`, would pass `same_bo_ic`) fail conservation with residuals over $500; `NearMissAcc` (bo `100`) fails conservation routing $4000 in against $9500 out; transactions over $10,000 are forced out of the motif by `amount_threshold_ic`; the alternative path through `IndividualX` (bo `300`) fails `same_bo_ic` against the cluster -- so they never appear in any solution.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── money_laundering_motif_detection.py
└── data/
    ├── accounts.csv
    └── transactions.csv
```

## How it works

The solver decides which transactions are in the motif and which accounts play which role. The headline patterns:

**Per-account flow conservation in *count* couples edge selection to role assignment.** Summing `Transaction.is_motif` per source account against `K * is_source + is_hub`, and per destination account against `is_hub + K * is_dest`, forces the solver into a structurally valid butterfly: source has out-degree K, each hub has out-degree 1 and in-degree 1, destination has in-degree K:

```python
out_flow_ic = model.where(Transaction.src == Account).require(
    sum(Transaction.is_motif).per(Transaction.src) == K * Account.is_source + Account.is_hub
)
in_flow_ic = model.where(Transaction.dst == Account).require(
    sum(Transaction.is_motif).per(Transaction.dst) == Account.is_hub + K * Account.is_dest
)
```

**Per-hub flow conservation in *amount* is the CSP signature -- this is the constraint a paths library cannot express.** For every account the solver assigns as a hub, the dollar amount it receives via motif edges must equal what it forwards, within `CONSERVATION_TOLERANCE_DOLLARS`. The `implies` form is the natural CSP encoding (a half-reified linear constraint) and reads as "if A is a hub, balance":

```python
T_in = Transaction.ref()
T_out = Transaction.ref()
conservation_pos_ic = model.where(T_in.dst == Account, T_out.src == Account).require(
    implies(
        Account.is_hub == 1,
        sum(T_in.amount_dollars * T_in.is_motif).per(T_in.dst)
        - sum(T_out.amount_dollars * T_out.is_motif).per(T_out.src)
        <= CONSERVATION_TOLERANCE_DOLLARS,
    )
)
```

**Filter framing keeps amount thresholds out of the decision aggregate.** The `where` clause filters at relational time to over-threshold rows; the constraint then forces those transactions out of the motif. Same shape for the same-beneficial-owner cluster filter on hub pairs:

```python
amount_threshold_ic = model.where(
    Transaction.amount_dollars >= AMOUNT_THRESHOLD_DOLLARS
).require(Transaction.is_motif == 0)
```

**Multi-solution enumeration surfaces every motif, not just the first.** Pass `solution_limit=MAX_MOTIFS` to `problem.solve(...)` and the solver enumerates up to that many distinct feasible assignments. Capturing the variable subconcept from `solve_for(...)` exposes a `.values(solution_index, value)` relationship that indexes the per-solution outputs; filtering on `value == 1` surfaces just the rows the solver picked into each motif. The populated property (e.g. `Transaction.is_motif`) reflects only the first solution, so for multi-solution output we always go through `.values(...)`:

```python
is_motif_var = problem.solve_for(
    Transaction.is_motif, type="bin", name=["is_motif", Transaction.tx_id]
)
# ... constraints ...
problem.solve("minizinc", time_limit_sec=60, solution_limit=MAX_MOTIFS)

sol_idx = Integer.ref()
val = Integer.ref()
model.select(
    sol_idx.alias("solution"),
    is_motif_var.transaction.tx_id.alias("tx_id"),
    is_motif_var.transaction.src.name.alias("src_name"),
    is_motif_var.transaction.dst.name.alias("dst_name"),
    is_motif_var.transaction.amount_dollars.alias("amount"),
).where(is_motif_var.values(sol_idx, val), val == 1).inspect()
```

The variable subconcept exposes a back-pointer field named after the entity in its property: `is_motif_var.transaction` walks back to the `Transaction` instance for each row. Same shape for `is_hub_var.account`, `is_source_var.account`, `is_dest_var.account`.

## Customize this template

- **Use your own data** by replacing the two CSV files with your accounts and transactions. The constraint structure does not change. `bo_id` should reflect your beneficial-ownership data; if you don't have it, set every row's `bo_id` to a single placeholder and drop `same_bo_ic`. Hub candidates need at least one incoming and one outgoing transaction in your graph (the source needs K outgoing, the destination K incoming) -- the count flow ICs only bind on accounts that appear on both sides of the transaction edges.
- **Raise the solution limit on a real ledger.** The bundled `MAX_MOTIFS = 10` is sized for the demo. On a production ledger with thousands of accounts you may want `MAX_MOTIFS = 100` (or higher) so the analyst inbox surfaces the full population of candidates. The `time_limit_sec` argument to `problem.solve` is your safety net -- enumeration stops when either the limit or the budget is reached.
- **Change the hub count** by adjusting `K` at the top of the script. K = 3 is the smallest count that's clearly a fan-out-then-fan-in pattern; real layering schemes often involve 5--20 hubs.
- **Tune the threshold and conservation tolerance** by editing `AMOUNT_THRESHOLD_DOLLARS` and `CONSERVATION_TOLERANCE_DOLLARS`. The FinCEN CTR threshold is $10,000. The default $100 tolerance is sized for this template's synthetic demo (residuals 20/25/80 fit comfortably) and for schemes with very small per-hop fees. Real-world layering often takes 1-3% per hop, so on $9,000 transactions you may want to widen the tolerance toward $200-300; tighten it if you're hunting near-perfect pass-through.
- **Drop conservation to recover a smurfing fan-in motif** -- the simpler "K under-threshold deposits converge on one destination" pattern. Remove the source role and the conservation IC, set per-account out-flow to `Account.is_smurf` (no source K-fan), and you get the smurfing detector with no source-side modelling.
- **Adapt to the K-cycle motif** (round-robin laundering: K accounts cycle money through a closed loop) by swapping the role binaries for a single `Account.is_in_cycle` binary and changing the per-account flow conservation in count to `out_count == in_count == is_in_cycle`. Per-hub conservation in amount carries over per-cycle-node.
- **Add a time-window filter** by adding a pairwise constraint over motif transactions. Declare two refs first (`T1 = Transaction.ref()`, `T2 = Transaction.ref()`), then: `model.where(T1.ts_minutes + WINDOW < T2.ts_minutes).require(T1.is_motif + T2.is_motif <= 1)`. Useful when your scheme runs on a known cadence (minutes for high-frequency layering; days or weeks for slower schemes).

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- The data may not contain a structurally valid butterfly. With `K = 3`, you need at least one account that fans out to three distinct accounts (under threshold each) which then converge on a single destination (under threshold each), where each hub's incoming amount matches its outgoing amount within `CONSERVATION_TOLERANCE_DOLLARS`. Relax constraints one at a time -- raise `CONSERVATION_TOLERANCE_DOLLARS`, raise `AMOUNT_THRESHOLD_DOLLARS`, drop `K` -- to confirm whether the data or a specific constraint is the bottleneck.
- Beneficial-ownership data inconsistencies: if every account has a unique `bo_id`, no pair of accounts can be hubs together (the `same_bo_ic` constraint forbids it). Confirm at least one cluster of K accounts shares a `bo_id`.
- All under-threshold transactions go to different destinations: the destination is forced to receive K motif transactions, so K under-threshold transactions must converge on the same recipient.

</details>

<details>
  <summary>How many motifs will the solver return?</summary>

- Up to `MAX_MOTIFS` (10 by default) or however many feasible motifs exist in the data, whichever is smaller. `solve_info().num_points` reports the actual count after the solve.
- Solution ordering is not guaranteed across runs or solver versions; the *set* of motifs is, but solution index 0 may swap with solution index 1 between runs. The K returned motifs are pairwise distinct on at least one decision but not maximally diverse and not ranked by laundered amount or any other severity score. Treat the `solution` column as a label, not a ranking.
- To get a ranked answer (e.g. surface the largest scheme first), switch to optimisation -- `problem.maximize(sum(Transaction.is_motif * Transaction.amount_dollars))` returns the motif with the largest total laundered amount under `solution_limit=1`; reverse with `minimize` for the smallest. For a top-K ranked list, run an iterative exclusion-cut loop (re-solve after forbidding each previous motif's edge set) or sort the enumerated motifs by total laundered amount in post-processing.

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
- HiGHS is not appropriate here -- this is a discrete satisfaction model with categorical decisions and structural propagation, not LP/MILP.

</details>
