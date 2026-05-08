---
title: "Money-Laundering Motif Detection"
description: "Detect layering motifs whose signature is constraint-arithmetic: a source routes under-threshold amounts through K beneficial-owner-clustered hubs, where each hub's incoming dollars must equal its outgoing dollars. The constraint a graph-pattern or paths library can't enforce."
featured: false
experience_level: intermediate
industry: "Banking"
reasoning_types:
  - Rules
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

Banking compliance and financial-crime teams hunt for "layering" -- a money-laundering pattern where a launderer routes funds from one source account through a cluster of intermediary accounts to a single destination, splitting each leg under the [FinCEN currency-transaction-report threshold](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1010/subpart-C/section-1010.311) of $10,000 so no transaction triggers a CTR filing. The intermediaries -- "hubs" -- share a beneficial owner: a single human or shell entity behind multiple accounts, who absorbs a small fee at each hop and forwards the rest.

The signal is not just structural. The structural pattern (one source fanning out to K hubs that converge on one destination) is what a graph-pattern matcher or a paths library handles well -- and what a launderer can hide behind by adding decoy edges and lookalike clusters. The signal that *separates* a layering motif from its lookalikes is **arithmetic across the chosen edges**: each hub's incoming dollar amount must equal its outgoing amount, within a tight tolerance. That balance condition has to hold *jointly* across whichever subset of transactions the detector picks, which is precisely the constraint a graph-pattern or paths library cannot enforce -- they see one edge or one walk at a time, not "this set of K edges, taken together, conserves flow at every hub." This template encodes that joint condition as a CSP and uses the solver to enumerate the motifs in the data that satisfy it.

The model decides which transactions are part of the motif and which accounts play which role (`is_source`, `is_hub`, `is_dest`). Per-account flow conservation in *count* couples edge-selection to role-assignment (graph reasoning can express this in isolation, but not while binding it to the arithmetic constraint below). Per-hub flow conservation in *dollar amounts* is the load-bearing CSP piece -- the solver must balance the chosen edges' values against each other, which a graph-pattern or paths library cannot express. Multi-solution enumeration (`solution_limit=K`) is available for batch analyst-triage workflows but is not the headline: the headline is the joint-arithmetic constraint.

The same pattern applies to other graph motif-detection problems where the signal is "K accounts in the same cluster forming a fixed shape with arithmetic balance across decision-selected edges": collusion rings in marketplace fraud, ration-card sharing in welfare fraud, recurring-billing abuse with fee splitting in subscription services. In every case, what makes the motif identifiable -- as opposed to "here are some accounts that look connected" -- is the constraint arithmetic.

## Who this is for

- Bank financial-crime / AML compliance teams investigating layering patterns
- Fintech risk engineers building structuring-detection alert pipelines
- Bank IT teams building investigative tools that surface candidate cases for human review
- Operations researchers learning subgraph motif enumeration with flow conservation as a CSP problem

## What you'll build

- A constraint model with four binary decision streams: `Transaction.is_motif` (which transactions are part of the motif) and `Account.is_source` / `Account.is_hub` / `Account.is_dest` (which accounts play which role)
- A role-eligibility pre-pass that forces the role bits to 0 on accounts that have no outgoing transactions (cannot be source or hub) or no incoming transactions (cannot be hub or destination), so the per-account flow ICs bind correctly even on customized ledgers with isolated accounts
- Per-account flow conservation in *count* over the directed transaction graph (source has out-degree K, each hub has in-degree 1 and out-degree 1, destination has in-degree K)
- **Per-hub flow conservation in *dollar amount* -- the load-bearing CSP IC.** Each hub forwards what it receives, within `CONSERVATION_TOLERANCE_DOLLARS`. Written with `implies` so the constraint activates only on accounts the solver picks as hubs -- no big-M coefficient. Per-hub residuals are visible in the motif-transactions inspection table; an analyst can confirm per hub that `sum(motif inflow) - sum(motif outflow)` is within tolerance.
- Same-beneficial-owner constraint over chosen hub pairs -- a pairwise constraint on the *selected* hub set, not just an edge filter
- Threshold predicate forcing each motif edge below the FinCEN $10K reporting line
- Transaction timestamps (`ts_minutes`) are loaded and printed for analyst review but are **not** part of the constraint set -- the model is a structural-and-arithmetic motif detector. Add a temporal-ordering IC in the customization section if your scheme requires hubs to receive before they forward.
- Multi-solution enumeration: `problem.solve(..., solution_limit=MAX_MOTIFS)` enumerates up to that many distinct feasible motifs; `Variable.values(solution_index, value)` surfaces every candidate. Useful for batch analyst-triage workflows on real ledgers.
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

The solver decides which transactions are in the motif and which accounts play which role. The model has three patterns -- one structural, one arithmetic, one pairwise -- and the arithmetic one is the reason this template uses CSP rather than graph reasoning.

**Pattern 1 -- per-account flow conservation in *count* couples edge selection to role assignment.** Summing `Transaction.is_motif` per source account against `K * is_source + is_hub`, and per destination account against `is_hub + K * is_dest`, forces the solver into a structurally valid butterfly: source has out-degree K, each hub has out-degree 1 and in-degree 1, destination has in-degree K. A graph-pattern matcher could express each side in isolation; a CSP binds the count-balance to the role assignment in a single declarative step.

```python
out_flow_ic = model.where(Transaction.src == Account).require(
    sum(Transaction.is_motif).per(Transaction.src) == K * Account.is_source + Account.is_hub
)
in_flow_ic = model.where(Transaction.dst == Account).require(
    sum(Transaction.is_motif).per(Transaction.dst) == Account.is_hub + K * Account.is_dest
)
```

**Pattern 2 -- per-hub flow conservation in *dollar amount*. This is the constraint a paths library cannot express.** For every account the solver assigns as a hub, the dollar amount it receives via motif edges must equal what it forwards, within `CONSERVATION_TOLERANCE_DOLLARS`. The constraint is arithmetic over a *decision-selected subset* of edges -- it cannot be evaluated until the solver has chosen which transactions are in the motif and which accounts are hubs. A path enumeration sees one walk at a time and never the joint condition; a rules-only encoding can sum-per-hub but cannot bind that sum to "and only over the chosen subset of edges, where the chosen accounts are hubs." The `implies` form below is the natural CSP encoding (a half-reified linear constraint) and reads as "if A is a hub, balance":

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

**Pattern 3 -- pairwise constraint on the *chosen* hub set.** The same-beneficial-owner constraint forbids any pair of accounts with different `bo_id`s from both being hubs in the same motif. This is a constraint over the *selected* subset, not an edge filter: an account is allowed to exist in a different `bo_id` cluster, but cannot be a hub *in this motif*. Two `Account.ref()` handles let the constraint range over ordered pairs, with `H1.id < H2.id` to avoid double-counting:

```python
H1 = Account.ref()
H2 = Account.ref()
same_bo_ic = model.where(H1.id < H2.id, H1.bo_id != H2.bo_id).require(
    H1.is_hub + H2.is_hub <= 1
)
```

**Solver call and enumeration.** `problem.solve(..., solution_limit=MAX_MOTIFS)` enumerates up to MAX_MOTIFS distinct feasible motifs. The variable subconcept returned by `solve_for(...)` exposes a `.values(solution_index, value)` relationship that indexes per-solution outputs; filtering on `value == 1` surfaces the rows the solver picked into each motif. The populated property (e.g. `Transaction.is_motif`) reflects only the first solution, so for multi-solution output the inspect blocks always go through `.values(...)`:

```python
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
- **Add a time-window filter** by adding a pairwise constraint over motif transactions. Declare two refs first (`T1 = Transaction.ref()`, `T2 = Transaction.ref()`), then: `model.where(T1.ts_minutes + WINDOW < T2.ts_minutes).require(T1.is_motif + T2.is_motif <= 1)`. Useful when your scheme runs on a known cadence (minutes for high-frequency layering; days or weeks for slower schemes).

### Variant motifs (different CSP techniques)

The butterfly above is the canonical scatter-gather pattern from the IBM AMLworld taxonomy ([Altman et al., NeurIPS 2023](https://arxiv.org/abs/2306.16424)). Two other layering shapes sit naturally in the same CSP framework but anchor *different* CSP techniques -- not just different topologies. Each variant lists the technique class explicitly so you can pick the one matching your investigation. Both are sketches, not full implementations.

| Motif | CSP technique | Why graph-pattern / paths / rules fall short |
|---|---|---|
| **Butterfly with per-hub conservation** (the runner above) | Per-vertex equality of two aggregates over decision-selected edge subsets | Paths see one walk; rules can sum-per-hub but cannot bind the equality to "the chosen subset of edges, where the chosen accounts are hubs" |
| **Smurf army with pairwise distinctness** (variant 1 below) | Pairwise constraints over decision-selected vertices, plus `all_different` on a vertex property | Paths/rules can filter pairs; only CSP enforces the pairwise property *over the K-subset the solver itself picks* |
| **Temporal burst with KYC-mix distribution** (variant 2 below) | Cardinality / distribution constraints over decision-selected vertex subsets | Rules can label each account's KYC tier; only CSP enforces the count distribution *over the selected subset* |

- **Variant 1 -- smurf army with pairwise distinctness on the selected set.** A known launder-target $T$ is moved into a destination via N source deposits, each below the FinCEN reporting threshold, summing to $T$ within tolerance. The K source accounts must have *pairwise-distinct beneficial owners* (no two are owned by the same human or shell entity -- the launderer recruits separate identities) and must *all* transact within a tight time window of each other (the burst signature). The decisions select which N source accounts the motif uses; the constraints bind only on the chosen accounts:

  ```python
  TARGET_DOLLARS = 27000  # known destination receipt
  TOLERANCE = 100
  WINDOW_MINUTES = 60
  Account.is_smurf = model.Property(f"{Account} is smurf if {Integer:is_smurf}")

  # Sum-equals-target over chosen smurfs
  sum_target_ic = model.where(Transaction.src.is_smurf == 1, Transaction.dst == DESTINATION).require(
      sum(Transaction.amount_dollars * Transaction.is_motif) >= TARGET_DOLLARS - TOLERANCE,
      sum(Transaction.amount_dollars * Transaction.is_motif) <= TARGET_DOLLARS + TOLERANCE,
  )

  # Pairwise: no two chosen smurfs share a beneficial owner (load-bearing CSP)
  S1 = Account.ref()
  S2 = Account.ref()
  pairwise_distinct_bo_ic = model.where(S1.id < S2.id, S1.bo_id == S2.bo_id).require(
      S1.is_smurf + S2.is_smurf <= 1
  )

  # Pairwise: chosen smurfs all transact within WINDOW_MINUTES of each other
  T1 = Transaction.ref()
  T2 = Transaction.ref()
  burst_window_ic = model.where(
      T1.src.is_smurf == 1, T2.src.is_smurf == 1,
      T1.tx_id < T2.tx_id,
      T2.ts_minutes - T1.ts_minutes > WINDOW_MINUTES,
  ).require(T1.is_motif + T2.is_motif <= 1)
  ```

  This is the structuring / smurf-army typology from FATF and FinCEN guidance. The pairwise constraints over the *chosen* subset are the CSP-required piece -- pre-filtered pair tables don't bind to "the K accounts the solver decides on."

- **Variant 2 -- temporal burst with KYC-mix distribution constraint.** N accounts transact within a short window AND within a tight amount band, with the *distribution* of selected accounts matching a target -- e.g., at least 4 retail-tier accounts, at most 1 business-tier, at least 3 distinct jurisdictions. The count-and-distribution constraints over the decision-selected subset are the CSP-required piece (a different technique from variant 1's pairwise constraints):

  ```python
  Account.kyc_tier = model.Property(f"{Account} has {String:kyc_tier}")
  Account.jurisdiction = model.Property(f"{Account} has {String:jurisdiction}")

  # Count distribution over the chosen subset
  retail_floor_ic = model.where(Account.kyc_tier == "retail").require(
      sum(Account.is_in_burst) >= 4
  )
  business_cap_ic = model.where(Account.kyc_tier == "business").require(
      sum(Account.is_in_burst) <= 1
  )
  # Plus: at least 3 distinct jurisdictions among chosen accounts (count over distinct values)
  ```

  This matches the "smurf army" KYC-tier-diverse profile and the temporal-coordination signal flagged in AML practitioner literature ([Tookitaki AML guidance](https://www.tookitaki.com/compliance-hub/smurfing-structuring-aml-detection-reporting)). Rules can mark a tier; only CSP enforces the *distribution* over the chosen subset.

These two variants are not in the runner -- the butterfly above demonstrates per-vertex aggregate equality, and adding two more motifs to one script would push it past the cart's "short and linear" convention. Use them as starting points for related collusion-ring / fee-splitting / coordinated-action detectors.

## References

- [Altman et al., *Realistic Synthetic Financial Transactions for Anti-Money Laundering Models*, NeurIPS 2023](https://arxiv.org/abs/2306.16424). The IBM AMLworld paper. Defines the canonical eight-pattern AML topology taxonomy (fan-in, fan-out, scatter-gather, gather-scatter, cycle, bipartite, stack, random) and explicitly notes "total in equals total out" for the conservation patterns -- the property the butterfly motif here encodes.
- [Starnini et al., *Smurf-Based Anti-Money Laundering in Time-Evolving Transaction Networks*, ECML PKDD 2021](https://link.springer.com/chapter/10.1007/978-3-030-86514-6_11). Time-window plus flow-balance signal in real-world transaction graphs (>180M transactions, >31M bank accounts).
- [Pareja et al., *The Shape of Money Laundering: Subgraph Representation*, arXiv:2404.19109](https://arxiv.org/pdf/2404.19109). Subgraph-classification benchmark on Elliptic2; multi-leg / multi-account topologies.
- [FATF (Financial Action Task Force) Typologies Reports](https://www.fatf-gafi.org/en/publications/Methodsandtrends.html) -- canonical typology source for placement / layering / integration stages, including the structuring and smurf-army patterns the variants above encode.
- [FinCEN Currency Transaction Report (CTR) regulation, 31 CFR § 1010.311](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1010/subpart-C/section-1010.311) -- the $10K reporting threshold whose evasion drives the structuring typology.

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
