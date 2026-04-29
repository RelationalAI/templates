---
title: "Money-Laundering Motif Detection"
description: "Detect smurfing fan-in patterns in a transaction graph using a CSP solver: K under-threshold transactions from a single beneficial-owner cluster into one destination, all within a tight time window."
featured: false
experience_level: intermediate
industry: "Banking"
reasoning_types:
  - Graph
  - Prescriptive
tags:
  - constraint-programming
  - graph-pattern-matching
  - banking
  - financial-crime
---

# Money-Laundering Motif Detection

## What this template is for

Banking compliance and financial-crime teams hunt for "smurfing" -- a money-laundering pattern where a single recipient receives many small deposits from a cluster of intermediary accounts, each transaction kept under the FinCEN reporting threshold ($10,000) so it never triggers a currency-transaction report (CTR). The intermediaries -- "smurfs" -- typically share a beneficial owner: a single human or shell entity behind multiple accounts. The signal is structural: K accounts in the same owner cluster fan into one destination inside a tight time window, and every transaction sits just under the threshold.

This template encodes the smurfing motif as a constraint satisfaction model. The solver decides which transactions are part of the motif and which accounts play which role (`is_smurf`, `is_dest`); flow-conservation constraints over the directed transaction graph couple edge-selection to role-assignment, so any returned solution is a structurally valid motif. Threshold and time-window predicates filter at relational time, so amounts never need to be aggregated across decision variables -- the model stays CSP-pure.

The same pattern applies to other graph motif-detection problems: collusion rings in marketplace fraud, ration-card sharing patterns in welfare fraud, recurring-billing abuse in subscription services -- any case where the signal is "K accounts in the same cluster forming a fixed shape against a single hub".

## Who this is for

- Bank financial-crime / AML compliance teams investigating layering patterns
- Fintech risk engineers building structuring-detection alert pipelines
- Bank IT teams building investigative tools that surface candidate cases for human review
- Operations researchers learning subgraph motif enumeration as a CSP problem

## What you'll build

- A constraint model with three binary decision streams: `Transaction.is_motif` (which transactions are part of the motif), `Account.is_smurf` and `Account.is_dest` (which accounts play which role)
- Per-account flow-conservation constraints over the directed transaction graph (each smurf has out-degree 1 in the motif; the destination has in-degree K)
- Filter-style threshold and time-window predicates encoded as `where`-filtered linear sums (no aggregation across decision variables)
- Same-beneficial-owner clustering encoded as a pairwise constraint
- Post-solve verification via `problem.verify()` confirming every named constraint holds in the returned solution

## What's included

- `money_laundering_motif_detection.py` -- main script with ontology, decisions, constraints, and solver call
- `data/accounts.csv` -- 8 accounts spanning four beneficial-owner clusters
- `data/transactions.csv` -- 10 directed transactions with amount and timestamp data
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

6. Expected output (the solver returns one feasible motif; the exact selection of smurfs may vary across runs and with different solver versions, since several account combinations satisfy the structural and ownership constraints):
   ```text
   Detected smurfing motif (one row per motif transaction):
     tx_id  src_account_id    src_name  dst_account_id           dst_name  amount  ts_min
         2               3   ShellAccB               1  WireRecipientCorp    9500      15
         3               4   ShellAccC               1  WireRecipientCorp    8500      12
         4               5   ShellAccD               1  WireRecipientCorp    7800      20

   Motif accounts (roles and beneficial owner):
     account_id               name  bo_id  is_dest  is_smurf
              1  WireRecipientCorp    500        1         0
              3          ShellAccB    100        0         1
              4          ShellAccC    100        0         1
              5          ShellAccD    100        0         1
   ```

   The destination `WireRecipientCorp` receives three under-threshold deposits from three smurf accounts, all sharing beneficial owner `100`, all within an 8-minute span.

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

**Per-account flow conservation couples edge selection to role assignment.** Summing `Transaction.is_motif` per source account and joining the result against `Account.is_smurf` is one constraint; the same shape against `Transaction.dst` and `K * Account.is_dest` is the other. These two ICs alone force the solver into a valid smurfing structure -- non-smurf accounts have zero outgoing motif edges, and only the destination receives the full K incoming edges:

```python
out_flow_ic = model.where(Transaction.src == Account).require(
    sum(Transaction.is_motif).per(Transaction.src) == Account.is_smurf
)
in_flow_ic = model.where(Transaction.dst == Account).require(
    sum(Transaction.is_motif).per(Transaction.dst) == K * Account.is_dest
)
```

**Filter framing keeps the model CSP-pure -- the threshold is a per-transaction predicate, never an aggregate over decisions.** The `where` clause filters at relational time to over-threshold rows; the constraint then forces those transactions out of the motif:

```python
amount_threshold_ic = model.where(
    Transaction.amount_dollars >= AMOUNT_THRESHOLD_DOLLARS
).require(Transaction.is_motif == 0)
```

**Pairwise constraints with `where`-side data filters are the cleanest way to express "for any two rows that violate condition X, at most one can be selected".** Time-window and same-beneficial-owner both follow this shape -- the data-side filter makes the constraint a small set of pure-arithmetic bounds, all re-evaluable by `problem.verify()`:

```python
T1 = Transaction.ref()
T2 = Transaction.ref()
time_window_ic = model.where(
    T1.ts_minutes + TIME_WINDOW_MINUTES < T2.ts_minutes,
).require(T1.is_motif + T2.is_motif <= 1)
```

## Customize this template

- **Use your own data** by replacing the two CSV files with your accounts and transactions. The constraint structure does not change. `bo_id` should reflect your beneficial-ownership data; if you don't have it, set every row's `bo_id` to a single placeholder and drop `same_bo_ic`.
- **Change the smurf count** by adjusting `K` at the top of the script. K = 3 is the smallest fan-in that's clearly a pattern; real cases often involve 5--20 smurfs.
- **Tune the threshold and window** by editing `AMOUNT_THRESHOLD_DOLLARS` and `TIME_WINDOW_MINUTES`. The FinCEN CTR threshold is $10,000; some banks set internal flagging thresholds lower. The window depends on the laundering tempo you're modelling -- minutes for high-frequency layering, days or weeks for slower schemes.
- **Adapt to the K-cycle motif** (round-robin laundering: K accounts cycle money through a closed loop) by swapping the role binaries (`is_smurf`, `is_dest`) for a single `Account.is_in_cycle` binary and changing the per-account flow conservation to `out_count == in_count == is_in_cycle`. Pairwise edge-existence is unchanged.
- **Adapt to the butterfly-cluster motif** (one source fans out to K hubs, each hub fans out to M leaves) by adding a third role binary (`is_hub`) and a second flow-conservation pair driving hub-to-leaf edges.

## Learn more

**Domain rule sources** (where the motif structure and threshold come from):
- FinCEN, [*Currency Transaction Report (CTR) requirements -- 31 CFR § 1010.311*](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1010/subpart-C/section-1010.311). The $10,000 threshold and structuring framing.
- Treasury / FinCEN, [*Structuring guidance*](https://www.fincen.gov/sites/default/files/shared/Final_Structuring_Brochure_-_For_Customers.pdf).

**Motif-detection technique** (the academic backbone for "find a small fixed subgraph in a large transaction graph"):
- Starnini et al., [*Smurf-Based Anti-Money-Laundering in Time-Evolving Transaction Networks*](https://www.isi.it/wp-content/uploads/2024/01/smurf-based-anti-money-laundering-in-time-evolving-transaction-networks_Starnini2021_Chapter_Smurf-BasedAnti-moneyLaunderin.pdf). The structural definition of smurfing in temporal transaction graphs.
- Pareja et al., [*The Shape of Money Laundering: Subgraph Representation Learning on the Blockchain*](https://arxiv.org/pdf/2404.19109). Subgraph patterns in laundering schemes.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- The data may not contain a structurally valid motif. With `K = 3`, you need at least one account that receives three under-threshold transactions from three distinct accounts that share a beneficial owner, all within `TIME_WINDOW_MINUTES`. Loosen the constraints (raise `AMOUNT_THRESHOLD_DOLLARS`, raise `TIME_WINDOW_MINUTES`, drop `K`) to confirm whether the data or the constraints are too tight.
- Beneficial-ownership data inconsistencies: if every account has a unique `bo_id`, no pair of accounts can be smurfs together (the `same_bo_ic` constraint forbids it). Confirm at least one cluster of K accounts shares a `bo_id`.
- All under-threshold transactions go to different destinations: the destination is forced to receive K motif transactions, so K under-threshold transactions must converge on the same recipient.

</details>

<details>
  <summary>Multiple feasible motifs exist; which one does the solver return?</summary>

- This is constraint satisfaction, not optimisation. Any valid motif is a correct answer; the solver is free to return different ones across runs.
- To enumerate all motifs (e.g., for an investigator queue), pass `solution_limit=N` to `problem.solve(...)` and iterate over `problem.num_points()` solutions.
- To pin a single answer, switch to optimisation -- e.g. `problem.minimize(sum(Transaction.is_motif * Transaction.amount_dollars))` returns the motif with the smallest total laundered amount.

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
