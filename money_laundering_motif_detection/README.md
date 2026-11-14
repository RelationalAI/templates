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

**This template detects three classes of layering motif on one shared transaction ledger using constraint-satisfaction (CSP) reasoning, which enforces such joint conditions across a solver-chosen subset of accounts and edges.** The three motifs share one ontology and deploy together as one model, with one report each:

| Motif | Joint condition it enforces | Topology | Model / report |
|---|---|---|---|
| **Butterfly** | Per-hub flow balance: each chosen hub's incoming dollars equal its outgoing dollars | Scatter-gather (one source -> K hubs -> one destination) | `model/butterfly.py` / `queries/butterfly_motifs.py` |
| **Smurf army** | Pairwise-distinct beneficial owners across the chosen cohort, plus a sum-to-target within a tight time window | Fan-in (K sources -> one destination) | `model/smurf_army.py` / `queries/smurf_army_motifs.py` |
| **KYC-mix burst** | Cardinality: at least a floor number of the chosen accounts are retail-tier | Fan-in within a tight time window | `model/kyc_burst.py` / `queries/kyc_burst_motifs.py` |

Each motif is grounded in a documented anti-money-laundering (AML) typology -- the eight-pattern taxonomy from [IBM AMLworld](https://arxiv.org/abs/2306.16424) (Altman et al., NeurIPS 2023) and the structuring / smurf-army typology from FATF and FinCEN (31 CFR § 1010.311). The same joint-condition patterns generalize beyond banking: per-hub flow balance surfaces collusion rings in marketplace fraud, pairwise distinctness surfaces identity-cohort scams in subscription services, and cardinality floors surface compliance-mix violations in regulatory audits.

## Who this is for

- Bank financial-crime / AML compliance teams investigating layering patterns
- Fintech risk engineers building structuring-detection alert pipelines
- Bank IT teams building investigative tools that surface candidate cases for human review
- Operations researchers learning multi-motif subgraph detection where each motif demonstrates a distinct CSP technique class

## What you'll build

A shared ontology in `model/ontology.py` and three CSP motifs, each adding its own decision properties and constraints to the same `Account` / `Transaction` model. Each motif configures a separate, named `Problem`; every refresh of the deployed model solves all three, and each motif's report prints its analyst-facing tables.

Shared ontology (in `model/ontology.py`):

- `Account` concept with `bo_id` (beneficial owner cluster), `kyc_tier`, and `jurisdiction` properties
- `Transaction` concept with `src`, `dst`, `amount_dollars`, `ts_minutes`

Each motif owns its own decisions and constraints. The bullets below summarise the integrity constraints per motif, with the load-bearing joint condition in bold; the "How it works" section walks each one with code.

- **Butterfly** (`model/butterfly.py`):
  - Decisions: `Transaction.is_motif`, `Account.is_source` / `is_hub` / `is_dest`
  - Per-account flow conservation in *count* (source out-degree K, hub in/out-degree 1, dest in-degree K)
  - Global motif-edge count (= 2K) -- closes a gap in the per-account ICs above for accounts with one-sided traffic (no outgoing or no incoming rows), where the per-account IC isn't instantiated and the role variables would otherwise be free
  - Layer constraints (no source-to-dest direct motif edge, no hub-to-hub motif edge) -- the count flow ICs admit non-butterfly shapes like `S->D, S->H1, S->H2, H1->H3, H2->D, H3->D` (still 2K edges, still 1-in / 1-out per hub) on customer ledgers that have under-threshold direct or hub-to-hub edges; these ICs forbid those shapes
  - **Per-hub flow conservation in dollar amount.** Each chosen hub's incoming dollars equal its outgoing dollars within `CONSERVATION_TOLERANCE_DOLLARS`. Written in big-M form (active when `is_hub == 1`, vacuous otherwise) with the M coefficient computed from the data.
  - Same-beneficial-owner pairwise filter over chosen hub pairs
  - Sub-threshold amount filter

- **Smurf army** (`model/smurf_army.py`):
  - Decisions: `Account.is_smurf`, `Transaction.is_smurf_tx`
  - Exactly N smurfs sending to a single target merchant
  - **Pairwise distinct beneficial owners** across chosen smurfs
  - Sum-equals-target on chosen smurf-tx amounts within tolerance
  - All chosen smurf-tx within `SMURF_WINDOW_MINUTES` of each other
  - Sub-threshold amount filter

- **KYC-mix burst** (`model/kyc_burst.py`):
  - Decisions: `Account.is_burst`, `Transaction.is_burst_tx`
  - Exactly N accounts in a coordinated burst to a single target merchant
  - **`>= RETAIL_FLOOR` retail-tier accounts among chosen** -- a cardinality constraint over the *selected* subset
  - All chosen burst-tx within `BURST_WINDOW_MINUTES` of each other
  - Sub-threshold amount filter

Multi-solution enumeration via `problem.configure(..., solution_limit=K)` is available on every motif for batch analyst-triage workflows. The butterfly and KYC-burst motifs exhaust to `OPTIMAL` on the bundled data; the smurf motif hits `SOLUTION_LIMIT` because pairwise-distinct beneficial-owner cohorts can swap any one chosen smurf for the dup-BO decoys (47 or 48), opening more cohorts than `MAX_SMURF_MOTIFS=5`. Raise the limit to enumerate further.

## What's included

- `model/` -- the model that `rai models deploy --path model` deploys:
  - `ontology.py` -- shared ontology (`Account`, `Transaction`) + CSV load. Every motif module imports the model from here and adds its own decisions and constraints on top.
  - `butterfly.py` -- per-hub flow conservation over a decision-selected edge subset.
  - `smurf_army.py` -- pairwise distinct beneficial owners + sum-target + tight time window.
  - `kyc_burst.py` -- cardinality on the chosen subset + tight time window.
- `queries/` -- one report per motif, printed from the deployed model: `butterfly_motifs.py`, `smurf_army_motifs.py`, `kyc_burst_motifs.py`.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the code itself.
- `data/accounts.csv` -- 90 accounts across 69 beneficial-owner clusters, including two butterfly-cluster hubs (`bo_id=100`, `bo_id=200`), a five-account smurf cohort with pairwise-distinct BOs (`bo_id=1701..1705`), a five-account KYC-mix burst cohort (4 retail + 1 business across 4 jurisdictions), plus dup-BO / out-of-window / over-amount decoys for each motif and 30 unrelated noise accounts.
- `data/transactions.csv` -- 138 directed transactions: 12 butterfly motif edges, 5 smurf motif edges, 5 KYC-burst motif edges, named decoys / cross-cluster traffic, and 60 noise transactions deterministically generated via `data/generate.py`.
- `data/generate.py` -- the deterministic generator that produced the bundled CSVs. Re-run only if you change the planted-motif design or want to regenerate at a different size; the template ships its outputs so users don't need to run it.
- `pyproject.toml` -- Python package configuration.

## Prerequisites

### Access
- A Snowflake account that has the RAI Native App installed.
- The one-time model deployment setup on that account, done by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) through **Governed setup**, **PAT authentication**, and steps 1-2 of **Additional setup for the prescriptive reasoner** (the Quickstart's setup block covers this template's own schema). It gives you a model role, a programmatic access token (PAT) stored as a secret, an external access integration, a PAT user, and a warehouse.
- A Snowflake user that holds the model role.

### Tools
- Python >= 3.10

## Quickstart

Before you start, install Python 3.10 or later, and have an account administrator complete the one-time model deployment setup described under Access.

Before the first deploy, create the internal schema as the model role, and have an administrator grant the RAI Native App caller access to it. The internal schema holds only this model's objects, so the grants cover all of it, including the solver's result tables that the deploy creates:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META;

-- as an administrator
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <PAT_WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META TO APPLICATION <RAI_APP_NAME>;
```

Run these steps from a terminal:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/money_laundering_motif_detection.zip). Unzip it and enter the template directory:

   ```bash
   unzip money_laundering_motif_detection.zip
   cd money_laundering_motif_detection
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the template's dependencies, including the `rai` CLI, in the active environment:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory, with the model role as the connection `role`.

   Then add the prescriptive reasoner and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     prescriptive:
       name: money_laundering_motif_detection_solver   # created on first deploy if it doesn't exist
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.MONEY_LAUNDERING_MOTIF_DETECTION   # published views and tables
     identity:
       internal_schema: <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META   # solver inputs, results, refresh procedures
     schedules:
       standard:
         interval_s: 0              # refresh only on deploy or on demand
     schedule: standard
     pat_secret: <PAT_SECRET>       # these four come from the setup page
     pat_eai: <PAT_EAI>
     pat_user: <PAT_USER>
     pat_warehouse: <PAT_WAREHOUSE>
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The model holds all three motifs. The deploy creates the public schema named in `raiconfig.yaml` if it doesn't exist and waits for the first refresh, which runs the three motif solves.

   Deploying again without changing the model applies no updates and does not solve again; the queries report the latest refresh. A change to a motif module or to its `problem.configure(...)` call redeploys, and the redeploy's refresh solves all three motifs.

6. **Query the results**

   Print each motif's report from the deployed model. The bundled dataset plants exactly the motifs each detector targets, plus dup-BO, out-of-window, and over-amount decoys for each. Solver build strings and exact wall times will vary; the structure of the output is stable:

   ```bash
   python -m queries.butterfly_motifs
   ```

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

   The butterfly search finds the two planted scatter-gathers (cluster `100` sending to `WireRecipientCorp`, cluster `200` sending to `OffshoreLLC`) and exhausts the search.

   ```bash
   python -m queries.smurf_army_motifs
   ```

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

   The smurf-army search hits `MAX_SMURF_MOTIFS=5` because the bundled data admits multiple sum-target cohorts: the planted five-distinct-BO cohort plus cohorts that swap one of the dup-BO decoys (47 or 48, both `bo_id=1706`) in for one of the planted smurfs. `distinct_bo_ic` is the constraint that prevents the 47, 48, and three-planted cohort, which sums in range, from being returned. The first cohort the solver enumerates is typically the planted one.

   ```bash
   python -m queries.kyc_burst_motifs
   ```

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

   The KYC-mix burst search finds two valid 5-account cohorts that satisfy the retail floor (4 retail, all within 60 min): the planted cohort with Brookline Industries plus an alternative-business swap (Newland Capital Inc).

   To solve again without changing the model, refresh the deployed model, then run the queries again:

   ```sql
   CALL <DB>.MONEY_LAUNDERING_MOTIF_DETECTION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

7. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The teardown removes the deployed objects and keeps the two schemas.

## Template structure
```text
.
├── README.md
├── pyproject.toml
├── model/
│   ├── __init__.py            # the deployed model: ontology + all three motifs
│   ├── ontology.py            # shared ontology + data load
│   ├── butterfly.py           # per-hub flow conservation
│   ├── smurf_army.py          # pairwise distinct BOs + sum-target
│   └── kyc_burst.py           # cardinality on chosen subset
├── queries/
│   ├── butterfly_motifs.py    # butterfly report
│   ├── smurf_army_motifs.py   # smurf-army report
│   └── kyc_burst_motifs.py    # KYC-mix burst report
└── data/
    ├── accounts.csv
    ├── transactions.csv
    └── generate.py            # deterministic generator (one-time, not runtime)
```

**Start here**: deploy with `rai models deploy --path model`, then run `python -m queries.butterfly_motifs` (or `smurf_army_motifs` / `kyc_burst_motifs`) for a motif report, or follow `runbook.md` to reproduce the template step by step with the RAI skills. Each motif module adds its own decisions and constraints to the shared ontology in `model/ontology.py`, and each motif is solved as its own `Problem`.

## Sample data

The bundled CSVs are synthetic and tuned so each of the three motifs is visible against realistic decoys. `data/generate.py` produced them deterministically; it ships alongside its outputs, so you do not need to run it. For production-style validation against a public dataset, see [Test against real public data](#customize-this-template).

- **`data/accounts.csv`** (90 rows) -- accounts across 69 beneficial-owner clusters, including two butterfly-cluster hubs (`bo_id=100`, `bo_id=200`), a five-account smurf cohort with pairwise-distinct owners (`bo_id=1701..1705`), a five-account KYC-mix burst cohort (4 retail + 1 business across 4 jurisdictions), plus dup-owner / out-of-window / over-amount decoys for each motif and 30 unrelated noise accounts.
- **`data/transactions.csv`** (138 rows) -- directed transactions: 12 butterfly motif edges, 5 smurf motif edges, 5 KYC-burst motif edges, named decoys, cross-cluster traffic, and 60 noise transactions.

## Model overview

All three motifs share one ontology, defined in `model/ontology.py`: `Account` vertices and `Transaction` directed edges. Each motif adds its own decision-valued properties (which account or transaction is part of the motif) on top of these base concepts.

- **Key entities**: `Account` (a bank account) and `Transaction` (a directed transfer between two accounts).
- **Primary identifiers**: integer `id` on `Account`; integer `tx_id` on `Transaction`.
- **Important invariants**: `Transaction.src` and `Transaction.dst` reference existing accounts; `amount_dollars` is positive; layering edges sit under the `AMOUNT_THRESHOLD_DOLLARS` CTR line (default `$10,000`); `ts_minutes` is non-negative.

`Account` carries `name`, `bo_id` (beneficial-owner cluster), `kyc_tier`, and `jurisdiction`; `Transaction` carries `src`, `dst`, `amount_dollars`, and `ts_minutes`. Each motif then adds its own motif-specific decision properties on top -- e.g. `Account.is_hub` / `is_smurf` / `is_burst` and `Transaction.is_motif` / `is_smurf_tx` / `is_burst_tx` -- populated by the solver. For the full concept and property definitions, see `model/ontology.py`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The three motifs share an `Account` / `Transaction` ontology defined in `model/ontology.py`. Each motif adds its own decision-valued properties, builds its own `Problem`, and constrains it with a different *class* of CSP technique. The "What you'll build" section above lists every constraint per motif; below is the load-bearing joint condition for each, with the part that rules / paths / graph reasoning cannot express called out explicitly.

**Butterfly: per-vertex aggregate equality over a decision-selected edge subset.** For every account the solver picks as a hub, the dollars it receives via motif edges must equal what it forwards, within `CONSERVATION_TOLERANCE_DOLLARS`. The constraint is arithmetic over a *decision-selected subset* of edges -- it cannot be evaluated until the solver has chosen which transactions are in the motif and which accounts are hubs. It is written in big-M form so it is active when an account is a hub and vacuous otherwise, with the M coefficient computed from the data. (Big-M rather than half-reification: a half-reified `implies` introduces a free Boolean auxiliary per non-hub account that the solver treats as search space, returning thousands of trivially-distinct solutions; big-M with a data-computed bound has no auxiliary, so enumeration stays clean and the solver exhausts after the data's actual motifs.) A path enumeration sees one walk at a time and never the joint condition; a rules-only encoding can sum-per-vertex but cannot bind that sum to "the chosen subset of edges, where the chosen accounts are hubs."

**Smurf army: pairwise constraints over a decision-selected vertex subset.** Among the N chosen smurfs, no two may share a beneficial owner. The constraint is over the *selected* subset, not an edge filter: an account may exist in the same `bo_id` cluster as another, but cannot be a smurf *in the same cohort*. A second account handle lets the constraint range over ordered pairs without double-counting. Pre-filtered pair tables can't bind to "the K-subset the solver itself picks." Combined with sum-equals-target on the chosen smurf-tx amounts and a tight pairwise time window, this motif's CSP shape is two joint conditions on the same chosen subset: the *sum* must hit a known launder target while the *pairwise distinctness* holds on the same chosen set.

**KYC-mix burst: cardinality over a decision-selected vertex subset.** Among the N chosen burst accounts, at least `RETAIL_FLOOR` must be retail-tier. Rules can label each account's tier; only CSP enforces the count *over the selected subset*. The launder-grade burst signature is "K accounts with a retail-tier floor transacting together in a tight window." A graph-pattern matcher can find the time-window cluster but has no way to express "and at least M of the chosen K are retail-tier."

**Solver call and enumeration.** Every motif configures the MiniZinc solver with a `solution_limit`. The variable subconcept returned by `solve_for(...)` exposes a per-solution values relationship; filtering on the chosen rows surfaces what the solver picked, since the populated property reflects only the first solution. These are pure satisfaction problems with no objective, so `status: OPTIMAL` means the solver enumerated all feasible motifs up to `solution_limit` -- not an optimisation verdict -- while `SOLUTION_LIMIT` means the limit was hit before enumeration exhausted (raise `MAX_*_MOTIFS` to surface more).

See `model/` for the implementation, `queries/` for the reports, and `runbook.md` for the skill-driven reproduction.

## Customize this template

### Use your own data

- Replace the two CSV files with your own accounts and transactions; every motif picks them up on the next deploy. The shared ontology in `model/ontology.py` reads columns by name (`id`, `name`, `bo_id`, `kyc_tier`, `jurisdiction`, `tx_id`, `src_id`, `dst_id`, `amount_dollars`, `ts_minutes`). Drop a column you don't have by deleting the corresponding `Account.<name> = model.Property(...)` line and any constraint that references it.
- Point the smurf and burst motifs at a different target merchant by editing `SMURF_TARGET_DESTINATION_ID` in `model/smurf_army.py` and `BURST_TARGET_DESTINATION_ID` in `model/kyc_burst.py`. On a real ledger you would set these from your watchlist of known-launder destinations.

**Test against real public data.** The bundled CSVs are synthetic and tuned to make the three motifs visible. For production-style validation, point the model at a slice of [IBM AMLworld HI-Small / LI-Small](https://github.com/IBM/AML-Data) (CDLA-Sharing-1.0; the dataset paper is Altman et al., NeurIPS 2023). AMLworld natively labels the eight-pattern taxonomy used in the butterfly motif (scatter-gather), and a 500-2000 transaction slice will solve in seconds. KYC tiers and jurisdictions are not in AMLworld natively; the smurf-army and KYC-burst motifs would need either synthetic augmentation columns or a different vertex category mapped from AMLworld's `Bank` / `Payment Format` columns.

### Tune parameters

- Edit the per-motif constants to tune the thresholds, then deploy again. The FinCEN CTR threshold (`AMOUNT_THRESHOLD_DOLLARS = 10_000`) lives in `model/ontology.py`. Per-hub conservation tolerance, smurf target dollars, smurf window, burst window, and retail floor are at the top of each motif's module in `model/`.
- Sweep the smurf target by parameterizing `SMURF_TARGET_DOLLARS` and re-running; alternatively, replace the equality with a minimum cumulative deposit constraint (`>= SMURF_TARGET_DOLLARS - tol`) if your watchlist tracks "at least $X laundered through this merchant" rather than a known exact total.

### Extend the model

- Add a temporal-ordering integrity constraint to the butterfly (so hubs must receive before they forward) by declaring two `Transaction.ref()` handles and a pairwise time constraint on hub-incoming vs hub-outgoing motif edges. Useful when your scheme runs on a known cadence.
- Add a jurisdiction-diversity floor to the KYC-mix burst with a per-jurisdiction sum plus a global count: declare an auxiliary `Account.is_burst_in_<j>` per jurisdiction `j` reified as `is_burst * (jurisdiction == j)`, then constrain the count of jurisdictions with at least one chosen account to be at least 3. The bundled data already plants four distinct jurisdictions in the burst cohort; this would make that distribution a hard constraint.

### Scale up / productionize

- Raise the solution limit on a real ledger. Each motif's `MAX_*_MOTIFS` is sized for the demo. On a production ledger with thousands of accounts you may want 100+ so the analyst inbox surfaces the full population of candidates. The `time_limit_sec` argument to `problem.configure` is your safety net.
- Pin `relationalai` to a known-good version for reproducible runs, and give the `standard` schedule in `raiconfig.yaml` a nonzero `interval_s` so the deployed model re-solves on a timer and candidate cases stay current for analyst triage.

## References

- [Altman et al., *Realistic Synthetic Financial Transactions for Anti-Money Laundering Models*, NeurIPS 2023](https://arxiv.org/abs/2306.16424). The IBM AMLworld paper. Defines the canonical eight-pattern AML topology taxonomy (fan-in, fan-out, scatter-gather, gather-scatter, cycle, bipartite, stack, random) and explicitly notes "total in equals total out" for the conservation patterns -- the property the butterfly motif here encodes. Public dataset releases at [IBM/AML-Data](https://github.com/IBM/AML-Data) under CDLA-Sharing-1.0.
- [Starnini et al., *Smurf-Based Anti-Money Laundering in Time-Evolving Transaction Networks*, ECML PKDD 2021](https://link.springer.com/chapter/10.1007/978-3-030-86514-6_11). Time-window plus flow-balance signal in real-world transaction graphs (>180M transactions, >31M bank accounts).
- [Pareja et al., *The Shape of Money Laundering: Subgraph Representation*, arXiv:2404.19109](https://arxiv.org/pdf/2404.19109). Subgraph-classification benchmark on Elliptic2; multi-leg / multi-account topologies.
- [FATF (Financial Action Task Force) Typologies Reports](https://www.fatf-gafi.org/en/publications/Methodsandtrends.html) -- canonical typology source for placement / layering / integration stages, including the structuring and smurf-army patterns the motifs encode.
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
  <summary>How many motifs / cohorts will each motif return?</summary>

- Up to `MAX_*_MOTIFS` (10/5/5 by default for butterfly/smurf/burst) or however many feasible motifs exist in the data, whichever is smaller. `solve_info().num_points` reports the actual count after the solve. On the bundled data, butterfly exhausts at 2 motifs and KYC-burst at 2 cohorts; the smurf motif hits the limit (5) because pairwise-distinct-BO cohorts can swap any chosen smurf for a dup-BO decoy that still sums in-range -- the `distinct_bo_ic` is the constraint that prevents the dup-BO cohort, and seeing it bind is the point of running the smurf demo.
- Solution ordering is not guaranteed across runs or solver versions; the *set* of motifs is, but solution index 0 may swap with solution index 1 between runs. Treat the `solution` column as a label, not a ranking.
- To get a ranked answer (e.g. surface the largest scheme first), switch to optimisation -- `problem.maximize(sum(Transaction.is_motif * Transaction.amount_dollars))` returns the motif with the largest total laundered amount under `solution_limit=1`. For a top-K ranked list, run an iterative exclusion-cut loop (re-solve after forbidding each previous motif's edge set) or sort the enumerated motifs in post-processing.

</details>

<details>
  <summary>Import error for <code>relationalai</code> or <code>model</code></summary>

- Confirm your virtual environment is active: `which python` should point to `.venv`.
- Reinstall dependencies: `python -m pip install .`.
- The reports import the `model` package from the template directory. Run `rai models deploy --path model` and `python -m queries.<name>` from inside the template directory, so the directory is on Python's path.

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

- [Prescriptive reasoner](https://docs.relational.ai/) -- the `Problem` API, decision variables, integrity constraints, and multi-solution enumeration with `solution_limit`, as all three motifs use.

## Support

- File issues at the RelationalAI templates repository.
