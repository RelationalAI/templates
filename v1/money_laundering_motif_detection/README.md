---
title: "Money-Laundering Motif Detection"
description: "Detect three classes of money-laundering layering motif on one transaction ledger using constraint-satisfaction (CSP) reasoning. Each motif enforces a joint condition across a solver-chosen subset of accounts and edges."
featured: false
experience_level: intermediate
industry: "Financial Services"
reasoning_types:
  - Prescriptive
tags:
  - constraint-programming
  - graph-pattern-matching
  - multi-solution
  - banking
  - financial-crime
---

## What this template is for

Banking compliance and financial-crime teams hunt for "layering" -- the obfuscation phase of money laundering, where a launderer routes funds across a coordinated cohort of intermediary accounts so no single transaction triggers a [FinCEN currency-transaction-report](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1010/subpart-C/section-1010.311) (CTR) filing. Launderers hide these schemes behind ordinary-looking transaction shapes, padding them with decoy edges and lookalike account clusters so the fraudulent cohort blends into the noise. What separates a real motif from its lookalikes is a condition that must hold jointly across the whole cohort the detector picks, not any single account or transaction on its own.

**This template detects three classes of layering motif on one shared transaction ledger using constraint-satisfaction (CSP) reasoning, which enforces such joint conditions across a solver-chosen subset of accounts and edges.** The three motifs run as independent scripts over a shared ontology:

| Motif | Joint condition it enforces | Topology | Runner |
|---|---|---|---|
| **Butterfly** | Per-hub flow balance: each chosen hub's incoming dollars equal its outgoing dollars | Scatter-gather (one source -> K hubs -> one destination) | `motif_butterfly.py` |
| **Smurf army** | Pairwise-distinct beneficial owners across the chosen cohort, plus a sum-to-target within a tight time window | Fan-in (K sources -> one destination) | `motif_smurf_army.py` |
| **KYC-mix burst** | Cardinality: at least a floor number of the chosen accounts are retail-tier | Fan-in within a tight time window | `motif_kyc_burst.py` |

Each motif is grounded in a documented anti-money-laundering (AML) typology -- the eight-pattern taxonomy from [IBM AMLworld](https://arxiv.org/abs/2306.16424) (Altman et al., NeurIPS 2023) and the structuring / smurf-army typology from FATF and FinCEN (31 CFR § 1010.311). The same joint-condition patterns generalize beyond banking: per-hub flow balance surfaces collusion rings in marketplace fraud, pairwise distinctness surfaces identity-cohort scams in subscription services, and cardinality floors surface compliance-mix violations in regulatory audits.

## Who this is for

- Bank financial-crime / AML compliance teams investigating layering patterns
- Fintech risk engineers building structuring-detection alert pipelines
- Bank IT teams building investigative tools that surface candidate cases for human review
- Operations researchers learning multi-motif subgraph detection where each motif demonstrates a distinct CSP technique class

## What you'll build

A shared ontology in `model_setup.py` and three independent CSP runners, each adding its own decision properties and constraints to the same `Account` / `Transaction` model. Every runner solves a separate `Problem` and prints the analyst-facing motif tables.

Shared ontology (in `model_setup.py`):

- `Account` concept with `bo_id` (beneficial owner cluster), `kyc_tier`, and `jurisdiction` properties
- `Transaction` concept with `src`, `dst`, `amount_dollars`, `ts_minutes`

Each motif owns its own decisions and constraints. The bullets below summarise the integrity constraints per motif, with the load-bearing joint condition in bold; the "How it works" section walks each one with code.

- **Butterfly** (`motif_butterfly.py`):
  - Decisions: `Transaction.is_motif`, `Account.is_source` / `is_hub` / `is_dest`
  - Per-account flow conservation in *count* (source out-degree K, hub in/out-degree 1, dest in-degree K)
  - Global motif-edge count (= 2K) -- closes a gap in the per-account ICs above for accounts with one-sided traffic (no outgoing or no incoming rows), where the per-account IC isn't instantiated and the role variables would otherwise be free
  - Layer constraints (no source-to-dest direct motif edge, no hub-to-hub motif edge) -- the count flow ICs admit non-butterfly shapes like `S->D, S->H1, S->H2, H1->H3, H2->D, H3->D` (still 2K edges, still 1-in / 1-out per hub) on customer ledgers that have under-threshold direct or hub-to-hub edges; these ICs forbid those shapes
  - **Per-hub flow conservation in dollar amount.** Each chosen hub's incoming dollars equal its outgoing dollars within `CONSERVATION_TOLERANCE_DOLLARS`. Written in big-M form (active when `is_hub == 1`, vacuous otherwise) with the M coefficient computed from the data.
  - Same-beneficial-owner pairwise filter over chosen hub pairs
  - Sub-threshold amount filter

- **Smurf army** (`motif_smurf_army.py`):
  - Decisions: `Account.is_smurf`, `Transaction.is_smurf_tx`
  - Exactly N smurfs sending to a single target merchant
  - **Pairwise distinct beneficial owners** across chosen smurfs
  - Sum-equals-target on chosen smurf-tx amounts within tolerance
  - All chosen smurf-tx within `SMURF_WINDOW_MINUTES` of each other
  - Sub-threshold amount filter

- **KYC-mix burst** (`motif_kyc_burst.py`):
  - Decisions: `Account.is_burst`, `Transaction.is_burst_tx`
  - Exactly N accounts in a coordinated burst to a single target merchant
  - **`>= RETAIL_FLOOR` retail-tier accounts among chosen** -- a cardinality constraint over the *selected* subset
  - All chosen burst-tx within `BURST_WINDOW_MINUTES` of each other
  - Sub-threshold amount filter

Multi-solution enumeration via `problem.solve(..., solution_limit=K)` is available on every runner for batch analyst-triage workflows. The butterfly and KYC-burst runners exhaust to `OPTIMAL` on the bundled data; the smurf runner hits `SOLUTION_LIMIT` because pairwise-distinct beneficial-owner cohorts can swap any one chosen smurf for the dup-BO decoys (47 or 48), opening more cohorts than `MAX_SMURF_MOTIFS=5`. Raise the limit to enumerate further.

## What's included

- `model_setup.py` -- shared ontology (`Account`, `Transaction`) + CSV load. Every motif runner imports `create_model()` and adds its own decisions and constraints on top.
- `motif_butterfly.py` -- per-hub flow conservation over a decision-selected edge subset.
- `motif_smurf_army.py` -- pairwise distinct beneficial owners + sum-target + tight time window.
- `motif_kyc_burst.py` -- cardinality on the chosen subset + tight time window.
- `data/accounts.csv` -- 90 accounts across 69 beneficial-owner clusters, including two butterfly-cluster hubs (`bo_id=100`, `bo_id=200`), a five-account smurf cohort with pairwise-distinct BOs (`bo_id=1701..1705`), a five-account KYC-mix burst cohort (4 retail + 1 business across 4 jurisdictions), plus dup-BO / out-of-window / over-amount decoys for each motif and 30 unrelated noise accounts.
- `data/transactions.csv` -- 138 directed transactions: 12 butterfly motif edges, 5 smurf motif edges, 5 KYC-burst motif edges, named decoys / cross-cluster traffic, and 60 noise transactions deterministically generated via `data/generate.py`.
- `data/generate.py` -- the deterministic generator that produced the bundled CSVs. Re-run only if you change the planted-motif design or want to regenerate at a different size; the template ships its outputs so users don't need to run it.
- `pyproject.toml` -- Python package configuration.

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

5. Run any of the three motif detectors. They share the bundled data and run independently:
   ```bash
   python motif_butterfly.py
   python motif_smurf_army.py
   python motif_kyc_burst.py
   ```

6. Expected output. The bundled dataset plants exactly the motifs each detector targets, plus dup-BO / out-of-window / over-amount decoys for each. Solver build strings and exact wall times will vary; the structure of the output is stable.

   `motif_butterfly.py` finds the two planted scatter-gathers (cluster `100` -> `WireRecipientCorp`, cluster `200` -> `OffshoreLLC`) and exhausts the search:
   ```text
   Solve result:
   • status: OPTIMAL
   • num_points: 2

   Result: 2 butterfly motif(s) found and search exhausted.

   Butterfly: chosen motif transactions (one row per motif edge per solution):
       solution  tx_id  src_account_id         src_name  dst_account_id           dst_name  amount  ts_min
   0          0      1               1  SourceShellCorp               2           HubAccA1    9000       5
   ...
   11         1     12               9         HubAccB3              10        OffshoreLLC    7780      44
   ```

   `motif_smurf_army.py` hits `MAX_SMURF_MOTIFS=5` because the bundled data admits multiple sum-target cohorts: the planted five-distinct-BO cohort plus cohorts that swap one of the dup-BO decoys (47 or 48, both `bo_id=1706`) in for one of the planted smurfs. `distinct_bo_ic` is the IC that prevents the {47, 48, + three planted} cohort -- which sums in-range -- from being returned. The first cohort enumerated by the solver is typically the planted one:
   ```text
   Solve result:
   • status: SOLUTION_LIMIT
   • num_points: 5

   Result: 5 smurf-army cohort(s) found; hit MAX_SMURF_MOTIFS=5.
            More may exist -- raise the limit to enumerate further.

   Smurf army: chosen smurf accounts per solution (with distinct BOs and jurisdictions):
      solution  smurf_id        smurf_name  bo_id  kyc_tier  jurisdiction
   0         0        42       Adrian Park   1701    retail            US
   1         0        43       Mira Volkov   1702    retail            UK
   2         0        44   Dimitri Solanki   1703   private        Cayman
   3         0        45       Sofia Reyes   1704    retail     Singapore
   4         0        46     Tomas Hellman   1705    retail       Germany
   ...
   ```

   `motif_kyc_burst.py` finds two valid 5-account cohorts that satisfy the retail floor (4 retail, all within 60 min) -- the planted cohort with Brookline Industries plus an alternative-business swap (Newland Capital Inc):
   ```text
   Solve result:
   • status: OPTIMAL
   • num_points: 2

   KYC-burst: chosen burst accounts per solution (with KYC tier and jurisdiction):
      solution  burst_id            burst_name  kyc_tier  jurisdiction  bo_id
   0         0        52           Trent Hayes    retail            US   2201
   1         0        53      Samira Choudhury    retail            UK   2202
   2         0        54           Diego Ramos    retail        Cayman   2203
   3         0        55            Nikhil Tan    retail     Singapore   2204
   4         0        56  Brookline Industries  business            US   2205
   5         1        52           Trent Hayes    retail            US   2201
   6         1        53      Samira Choudhury    retail            UK   2202
   7         1        54           Diego Ramos    retail        Cayman   2203
   8         1        55            Nikhil Tan    retail     Singapore   2204
   9         1        57   Newland Capital Inc  business       Germany   2206
   ```

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── model_setup.py             # shared ontology + data load
├── motif_butterfly.py         # per-hub flow conservation
├── motif_smurf_army.py        # pairwise distinct BOs + sum-target
├── motif_kyc_burst.py         # cardinality on chosen subset
└── data/
    ├── accounts.csv
    ├── transactions.csv
    └── generate.py            # deterministic generator (one-time, not runtime)
```

**Start here**: run `python motif_butterfly.py` (or `motif_smurf_army.py` / `motif_kyc_burst.py`). Each is self-contained -- it imports the shared ontology from `model_setup.py`, loads the bundled data, and solves its own motif independently.

## Sample data

The bundled CSVs are synthetic and tuned so each of the three motifs is visible against realistic decoys. `data/generate.py` produced them deterministically; it ships alongside its outputs, so you do not need to run it. For production-style validation against a public dataset, see [Test against real public data](#customize-this-template).

- **`data/accounts.csv`** (90 rows) -- accounts across 69 beneficial-owner clusters, including two butterfly-cluster hubs (`bo_id=100`, `bo_id=200`), a five-account smurf cohort with pairwise-distinct owners (`bo_id=1701..1705`), a five-account KYC-mix burst cohort (4 retail + 1 business across 4 jurisdictions), plus dup-owner / out-of-window / over-amount decoys for each motif and 30 unrelated noise accounts.
- **`data/transactions.csv`** (138 rows) -- directed transactions: 12 butterfly motif edges, 5 smurf motif edges, 5 KYC-burst motif edges, named decoys, cross-cluster traffic, and 60 noise transactions.

## Model overview

All three runners share one ontology, defined in `model_setup.py`: `Account` vertices and `Transaction` directed edges. Each runner adds its own decision-valued properties (which account or transaction is part of the motif) on top of these base concepts at solve time.

- **Key entities**: `Account` (a bank account) and `Transaction` (a directed transfer between two accounts).
- **Primary identifiers**: integer `id` on `Account`; integer `tx_id` on `Transaction`.
- **Important invariants**: `Transaction.src` and `Transaction.dst` reference existing accounts; `amount_dollars` is positive; layering edges sit under the `AMOUNT_THRESHOLD_DOLLARS` CTR line (default `$10,000`); `ts_minutes` is non-negative.

**`Account`** -- a bank account, and a vertex in the transaction graph.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `id` | Integer | Yes | Loaded from `data/accounts.csv` |
| `name` | String | No | Human-readable account name |
| `bo_id` | Integer | No | Beneficial-owner cluster; accounts sharing a `bo_id` share an owner |
| `kyc_tier` | String | No | Know-your-customer tier (`retail` / `business` / `private`) |
| `jurisdiction` | String | No | Account jurisdiction (e.g. `US`, `UK`, `Cayman`) |

Each runner also adds motif-specific decision properties -- e.g. `Account.is_hub` (butterfly), `Account.is_smurf` (smurf army), `Account.is_burst` (KYC-mix burst) -- populated by the solver.

**`Transaction`** -- a directed transfer, and an edge in the graph.

| Property | Type | Identifying? | Notes |
|---|---|---|---|
| `tx_id` | Integer | Yes | Loaded from `data/transactions.csv` |
| `src` | `Account` | No | Sending account (from `src_id`) |
| `dst` | `Account` | No | Receiving account (from `dst_id`) |
| `amount_dollars` | Integer | No | Transfer amount in USD |
| `ts_minutes` | Integer | No | Timestamp in minutes; drives the time-window constraints |

Each runner adds a motif-specific edge decision -- e.g. `Transaction.is_motif` (butterfly), `Transaction.is_smurf_tx` (smurf army), `Transaction.is_burst_tx` (KYC-mix burst) -- populated by the solver.

## How it works

The three motifs share an `Account` / `Transaction` ontology defined in `model_setup.py`. Each runner adds its own decision-valued properties, builds its own `Problem`, and constrains it with a different *class* of CSP technique. The "What you'll build" section above lists every constraint per motif; below is the load-bearing CSP IC for each, with the part that rules / paths / graph reasoning cannot express called out explicitly.

### Butterfly: per-vertex aggregate equality over a decision-selected edge subset

For every account the solver picks as a hub, the dollar amount it receives via motif edges must equal what it forwards, within `CONSERVATION_TOLERANCE_DOLLARS`. The constraint is arithmetic over a *decision-selected subset* of edges -- it cannot be evaluated until the solver has chosen which transactions are in the motif and which accounts are hubs. Written in big-M form so the constraint is active when `is_hub == 1` and vacuous when `is_hub == 0`, with the M coefficient computed from the data:

```python
T_out = Transaction.ref()
conservation_pos_ic = model.where(Transaction.dst == Account, T_out.src == Account).require(
    sum(Transaction.amount_dollars * Transaction.is_motif).per(Transaction.dst)
    - sum(T_out.amount_dollars * T_out.is_motif).per(T_out.src)
    + CONSERVATION_BIG_M * Account.is_hub
    <= CONSERVATION_TOLERANCE_DOLLARS + CONSERVATION_BIG_M
)
```

A path enumeration sees one walk at a time and never the joint condition; a rules-only encoding can sum-per-vertex but cannot bind that sum to "the chosen subset of edges, where the chosen accounts are hubs."

> We use big-M rather than a half-reified `implies(Account.is_hub == 1, ...)` for this constraint. Half-reification introduces a free Boolean auxiliary per non-hub account that MiniZinc treats as part of the search space, returning thousands of trivially-distinct solutions for the same role/motif assignment. Big-M with a data-computed bound has no auxiliary, so enumeration stays clean and the solver exhausts after the data's actual motifs.

### Smurf army: pairwise constraints over a decision-selected vertex subset

Among the N chosen smurfs, no two may share a beneficial owner. The constraint is over the *selected* subset, not an edge filter: an account is allowed to exist in the same `bo_id` cluster as another, but cannot be a smurf *in the same cohort*. A second `Account.ref()` handle plus the bare `Account` lets the constraint range over ordered pairs, with `Account.id < S2.id` to avoid double-counting:

```python
S2 = Account.ref()
distinct_bo_ic = model.where(Account.id < S2.id, Account.bo_id == S2.bo_id).require(
    Account.is_smurf + S2.is_smurf <= 1
)
```

Pre-filtered pair tables can't bind to "the K-subset the solver itself picks." Combined with sum-equals-target on the chosen smurf-tx amounts and a tight pairwise time window, this motif's CSP shape is two joint conditions on the same chosen subset: the *sum* must hit a known launder target while the *pairwise distinctness* holds on the same chosen set.

### KYC-mix burst: cardinality over a decision-selected vertex subset

Among the N chosen burst accounts, at least `RETAIL_FLOOR` must be retail-tier. Rules can label each account's tier; only CSP enforces the count *over the selected subset*:

```python
retail_floor_ic = model.require(
    sum(Account.is_burst).where(Account.kyc_tier == "retail") >= RETAIL_FLOOR
)
```

The launder-grade burst signature is "K accounts with a retail-tier floor transacting together in a tight window." A graph-pattern matcher can find the time-window cluster but has no way to express "and at least M of the chosen K are retail-tier."

### Solver call and enumeration

Every runner calls `problem.solve("minizinc", time_limit_sec=60, solution_limit=...)`. The variable subconcept returned by `solve_for(...)` exposes a `.values(solution_index, value)` relationship that indexes per-solution outputs; filtering on `value == 1` surfaces the rows the solver picked. The populated property reflects only the first solution, so for multi-solution output the inspect blocks always go through `.values(...)`.

These are pure satisfaction problems with no objective, so `status: OPTIMAL` in the `solve_info().display()` output means the solver enumerated all feasible motifs up to `solution_limit`. It is not an optimisation verdict. `SOLUTION_LIMIT` means the limit was hit before enumeration exhausted -- raise `MAX_*_MOTIFS` to surface more.

## Customize this template

### Use your own data

- Replace the two CSV files with your own accounts and transactions; every runner picks them up automatically. The shared ontology in `model_setup.py` reads columns by name (`id`, `name`, `bo_id`, `kyc_tier`, `jurisdiction`, `tx_id`, `src_id`, `dst_id`, `amount_dollars`, `ts_minutes`). Drop a column you don't have by deleting the corresponding `Account.<name> = model.Property(...)` line and any constraint that references it.
- Point the smurf and burst runners at a different target merchant by editing `SMURF_TARGET_DESTINATION_ID` in `motif_smurf_army.py` and `BURST_TARGET_DESTINATION_ID` in `motif_kyc_burst.py`. On a real ledger you would set these from your watchlist of known-launder destinations.

**Test against real public data.** The bundled CSVs are synthetic and tuned to make the three motifs visible. For production-style validation, point the runners at a slice of [IBM AMLworld HI-Small / LI-Small](https://github.com/IBM/AML-Data) (CDLA-Sharing-1.0; the dataset paper is Altman et al., NeurIPS 2023). AMLworld natively labels the eight-pattern taxonomy used in the butterfly motif (scatter-gather), and a 500-2000 transaction slice will solve in seconds. KYC tiers and jurisdictions are not in AMLworld natively; the smurf-army and KYC-burst runners would need either synthetic augmentation columns or a different vertex category mapped from AMLworld's `Bank` / `Payment Format` columns.

### Tune parameters

- Edit the per-runner constants to tune the thresholds. The FinCEN CTR threshold (`AMOUNT_THRESHOLD_DOLLARS = 10_000`) lives in `model_setup.py`. Per-hub conservation tolerance, smurf target dollars, smurf window, burst window, and retail floor are at the top of each motif's runner.
- Sweep the smurf target by parameterizing `SMURF_TARGET_DOLLARS` and re-running; alternatively, replace the equality with a minimum cumulative deposit constraint (`>= SMURF_TARGET_DOLLARS - tol`) if your watchlist tracks "at least $X laundered through this merchant" rather than a known exact total.

### Extend the model

- Add a temporal-ordering integrity constraint to the butterfly (so hubs must receive before they forward) by declaring two `Transaction.ref()` handles and a pairwise time constraint on hub-incoming vs hub-outgoing motif edges. Useful when your scheme runs on a known cadence.
- Add a jurisdiction-diversity floor to the KYC-mix burst with a per-jurisdiction sum plus a global count: declare an auxiliary `Account.is_burst_in_<j>` per jurisdiction `j` reified as `is_burst * (jurisdiction == j)`, then constrain the count of jurisdictions with at least one chosen account to be at least 3. The bundled data already plants four distinct jurisdictions in the burst cohort; this would make that distribution a hard constraint.

### Scale up / productionize

- Raise the solution limit on a real ledger. Each runner's `MAX_*_MOTIFS` is sized for the demo. On a production ledger with thousands of accounts you may want 100+ so the analyst inbox surfaces the full population of candidates. The `time_limit_sec` argument to `problem.solve` is your safety net.
- Pin `relationalai` to a known-good version for reproducible runs, and schedule the runners after each ledger refresh so candidate cases stay current for analyst triage.

## References

- [Altman et al., *Realistic Synthetic Financial Transactions for Anti-Money Laundering Models*, NeurIPS 2023](https://arxiv.org/abs/2306.16424). The IBM AMLworld paper. Defines the canonical eight-pattern AML topology taxonomy (fan-in, fan-out, scatter-gather, gather-scatter, cycle, bipartite, stack, random) and explicitly notes "total in equals total out" for the conservation patterns -- the property the butterfly motif here encodes. Public dataset releases at [IBM/AML-Data](https://github.com/IBM/AML-Data) under CDLA-Sharing-1.0.
- [Starnini et al., *Smurf-Based Anti-Money Laundering in Time-Evolving Transaction Networks*, ECML PKDD 2021](https://link.springer.com/chapter/10.1007/978-3-030-86514-6_11). Time-window plus flow-balance signal in real-world transaction graphs (>180M transactions, >31M bank accounts).
- [Pareja et al., *The Shape of Money Laundering: Subgraph Representation*, arXiv:2404.19109](https://arxiv.org/pdf/2404.19109). Subgraph-classification benchmark on Elliptic2; multi-leg / multi-account topologies.
- [FATF (Financial Action Task Force) Typologies Reports](https://www.fatf-gafi.org/en/publications/Methodsandtrends.html) -- canonical typology source for placement / layering / integration stages, including the structuring and smurf-army patterns the motif runners encode.
- [FinCEN Currency Transaction Report (CTR) regulation, 31 CFR § 1010.311](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1010/subpart-C/section-1010.311) -- the $10K reporting threshold whose evasion drives the structuring typology.
- [Tookitaki, *Smurfing and Structuring: AML Detection and Reporting*](https://www.tookitaki.com/compliance-hub/smurfing-structuring-aml-detection-reporting). Practitioner guidance on the KYC-tier-diverse smurf-army profile that the KYC-mix burst motif encodes.

## Troubleshooting

<details>
  <summary>Solver returns INFEASIBLE</summary>

- **Check data quality first when using your own CSVs.** Five silent failure modes can produce INFEASIBLE or spurious motifs without any error message: (a) **dangling foreign keys** -- `src_id` or `dst_id` values not present in `accounts.csv` are silently dropped from `Transaction.src` / `Transaction.dst`, narrowing the edge graph; (b) **duplicate primary keys** -- duplicate `id` in `accounts.csv` or `tx_id` in `transactions.csv` collapse rows on the identify-by join, discarding all but one row's property values; (c) **self-loop transactions** (`src_id == dst_id`) -- the same account satisfies both source and destination roles, which can trivially clear flow-conservation ICs with no actual flow; (d) **non-positive amounts** -- zero or negative `amount_dollars` passes the `< AMOUNT_THRESHOLD_DOLLARS` filter, admitting economically meaningless motif edges; (e) **negative timestamps** -- shift the burst/window IC arithmetic. A quick pandas sanity check before running: `assert acc["id"].is_unique`, `assert tx["tx_id"].is_unique`, `assert tx["src_id"].isin(acc["id"]).all()`, `assert tx["dst_id"].isin(acc["id"]).all()`, `assert (tx["src_id"] != tx["dst_id"]).all()`, `assert (tx["amount_dollars"] > 0).all()`, `assert (tx["ts_minutes"] >= 0).all()`.
- The data may not contain a structurally valid instance of the motif you ran. For the butterfly, you need at least one account that fans out to K distinct accounts (under threshold each) which then converge on a single destination, where each hub's incoming amount matches its outgoing within `CONSERVATION_TOLERANCE_DOLLARS`. For the smurf army, you need N source accounts with pairwise-distinct BOs whose deposits to a single target sum to `SMURF_TARGET_DOLLARS` within tolerance and all fall within `SMURF_WINDOW_MINUTES`. For the KYC-mix burst, you need N accounts to a single target whose retail-tier count satisfies the floor constraint and all fall within `BURST_WINDOW_MINUTES`.
- Confirm the target-merchant id (`SMURF_TARGET_DESTINATION_ID`, `BURST_TARGET_DESTINATION_ID`) matches an account that actually receives the candidate edges in your data.
- Relax constraints one at a time (raise tolerance / window, drop K, raise the threshold) to confirm whether the data or a specific constraint is the bottleneck.
- Beneficial-ownership data inconsistencies: for the butterfly, if every account has a unique `bo_id` no pair can be hubs together; for the smurf army the opposite -- with too many accounts sharing a `bo_id` you may not get N pairwise-distinct candidates.
- KYC-mix burst data inconsistencies: if no four candidate accounts to the target are retail-tier, the retail floor is unreachable.

</details>

<details>
  <summary>How many motifs / cohorts will each runner return?</summary>

- Up to `MAX_*_MOTIFS` (10/5/5 by default for butterfly/smurf/burst) or however many feasible motifs exist in the data, whichever is smaller. `solve_info().num_points` reports the actual count after the solve. On the bundled data, butterfly exhausts at 2 motifs and KYC-burst at 2 cohorts; the smurf runner hits the limit (5) because pairwise-distinct-BO cohorts can swap any chosen smurf for a dup-BO decoy that still sums in-range -- the `distinct_bo_ic` is the constraint that prevents the dup-BO cohort, and seeing it bind is the point of running the smurf demo.
- Solution ordering is not guaranteed across runs or solver versions; the *set* of motifs is, but solution index 0 may swap with solution index 1 between runs. Treat the `solution` column as a label, not a ranking.
- To get a ranked answer (e.g. surface the largest scheme first), switch to optimisation -- `problem.maximize(sum(Transaction.is_motif * Transaction.amount_dollars))` returns the motif with the largest total laundered amount under `solution_limit=1`. For a top-K ranked list, run an iterative exclusion-cut loop (re-solve after forbidding each previous motif's edge set) or sort the enumerated motifs in post-processing.

</details>

<details>
  <summary>Import error for <code>relationalai</code> or <code>model_setup</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.
- The motif runners import from `model_setup` as a sibling module. Run them from inside the template directory (so the directory is on Python's path) or `python -m motif_butterfly` from the parent.

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

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) -- `model.where(...)`, `.require(...)`, aggregates, and `.ref()` handles for ranging over pairs and subsets.

### Reasoner reference

- [Prescriptive reasoner](https://docs.relational.ai/) -- the `Problem` API, decision variables, integrity constraints, and multi-solution enumeration with `solution_limit`, as all three motif runners use.

## Support

- File issues at the RelationalAI templates repository.
