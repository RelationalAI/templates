---
title: "Money-Laundering Motif Detection"
description: "Detect layering 'butterfly' patterns in a transaction graph using a CSP solver: a source routing under-threshold amounts through K beneficial-owner-clustered hubs to a single destination, with per-hub flow conservation in dollar amounts."
featured: false
experience_level: intermediate
industry: "Banking"
reasoning_types:
  - Rules-based
  - Prescriptive
tags:
  - constraint-programming
  - graph-pattern-matching
  - banking
  - financial-crime
---

# Money-Laundering Motif Detection

## What this template is for

Banking compliance and financial-crime teams hunt for "layering" -- a money-laundering pattern where a launderer routes funds from one source account through a cluster of intermediary accounts to a single destination, splitting each leg under the [FinCEN currency-transaction-report threshold](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1010/subpart-C/section-1010.311) of $10,000 so no transaction triggers a CTR filing. The intermediaries -- "hubs" -- share a beneficial owner: a single human or shell entity behind multiple accounts, who absorbs a small fee at each hop and forwards the rest. The signal is structural and arithmetic: K hubs receive from the source and forward to a destination, where each hub's incoming dollar amount equals its outgoing amount within a tight tolerance.

This template encodes the layering motif as a constraint satisfaction model. The solver decides which transactions are part of the motif and which accounts play which role (`is_source`, `is_hub`, `is_dest`); per-account flow conservation in count couples edge-selection to role-assignment, while per-hub flow conservation in *dollar amounts* pulls the model beyond pure pattern-matching -- the solver must balance the chosen edges' values against each other, which is the CSP arithmetic that a graph-pattern / paths library cannot express.

The same pattern applies to other graph motif-detection problems where the signal is "K accounts in the same cluster forming a fixed shape with arithmetic balance across decision-selected edges": collusion rings in marketplace fraud, ration-card sharing in welfare fraud, recurring-billing abuse with fee splitting in subscription services.

## Who this is for

- Bank financial-crime / AML compliance teams investigating layering patterns
- Fintech risk engineers building structuring-detection alert pipelines
- Bank IT teams building investigative tools that surface candidate cases for human review
- Operations researchers learning subgraph motif enumeration with flow conservation as a CSP problem

## What you'll build

- A constraint model with four binary decision streams: `Transaction.is_motif` (which transactions are part of the motif) and `Account.is_source` / `Account.is_hub` / `Account.is_dest` (which accounts play which role)
- Per-account flow conservation in *count* over the directed transaction graph (source has out-degree K, each hub has in-degree 1 and out-degree 1, destination has in-degree K)
- Per-hub flow conservation in *dollar amount*: each hub forwards what it receives, within `CONSERVATION_TOLERANCE_DOLLARS`. Written with `implies` so the constraint activates only on accounts the solver picks as hubs -- no big-M coefficient
- Filter-style threshold and same-beneficial-owner predicates encoded as `where`-filtered linear constraints
- Post-solve verification via `problem.verify()` re-evaluating the relational arithmetic constraints in the returned solution (the implies-bodied conservation ICs are solver-only and omitted)

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

6. Expected output (the dataset contains two complete butterflies -- one in beneficial-owner cluster `100` against `WireRecipientCorp`, and one in cluster `200` against `OffshoreLLC`; the solver returns one of them, so the exact selection may vary across runs and solver versions):
   ```text
   Detected layering motif (one row per motif transaction):
     tx_id  src_account_id          src_name  dst_account_id           dst_name  amount  ts_min
         1               1   SourceShellCorp               2           HubAccA1    9000       5
         2               1   SourceShellCorp               3           HubAccA2    8500       7
         3               1   SourceShellCorp               4           HubAccA3    9500       9
         4               2          HubAccA1               5  WireRecipientCorp    8980      15
         5               3          HubAccA2               5  WireRecipientCorp    8475      17
         6               4          HubAccA3               5  WireRecipientCorp    9420      19

   Motif accounts (roles and beneficial owner):
     account_id               name  bo_id  is_source  is_hub  is_dest
              1    SourceShellCorp    600          1       0        0
              2           HubAccA1    100          0       1        0
              3           HubAccA2    100          0       1        0
              4           HubAccA3    100          0       1        0
              5  WireRecipientCorp    700          0       0        1

   Per-hub conservation residuals (in_amount - out_amount, must be in [-tolerance, +tolerance]):
     hub_id  hub_name  in_amount  out_amount
          2  HubAccA1       9000        8980
          3  HubAccA2       8500        8475
          4  HubAccA3       9500        9420
   ```

   The detected motif is a source account routing three under-threshold deposits through three hub accounts (all sharing one beneficial owner) to a single destination. Each hub absorbs a small "fee" residual within the `CONSERVATION_TOLERANCE_DOLLARS` ($100) bound before forwarding the balance. The dataset's near-misses make the constraints visibly do work: alt-cluster-100 candidates `AltCluster100A` and `AltCluster100B` (bo `100`, would pass `same_bo_ic`) fail conservation with residuals over $500; `NearMissAcc` (bo `100`) fails conservation routing $4000 in against $9500 out; transactions over $10,000 are forced out of the motif by `amount_threshold_ic`; the alternative path through `IndividualX` (bo `300`) fails `same_bo_ic` against the cluster.

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

## Customize this template

- **Use your own data** by replacing the two CSV files with your accounts and transactions. The constraint structure does not change. `bo_id` should reflect your beneficial-ownership data; if you don't have it, set every row's `bo_id` to a single placeholder and drop `same_bo_ic`. Hub candidates need at least one incoming and one outgoing transaction in your graph (the source needs K outgoing, the destination K incoming) -- the count flow ICs only bind on accounts that appear on both sides of the transaction edges.
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
  <summary>Multiple feasible motifs exist; which one does the solver return?</summary>

- This is constraint satisfaction, not optimization. Any valid motif is a correct answer; the solver is free to return different ones across runs.
- To enumerate all motifs (e.g., for an investigator queue), pass `solution_limit=N` to `problem.solve(...)` and iterate over `problem.num_points()` solutions.
- To pin a single answer, switch to optimization -- e.g. `problem.minimize(sum(Transaction.is_motif * Transaction.amount_dollars))` returns the motif with the smallest total laundered amount; or maximize to surface the largest scheme.

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
