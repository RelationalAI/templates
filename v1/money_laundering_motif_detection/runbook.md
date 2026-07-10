# Money Laundering Motif Detection — Analyst Runbook

An AML investigator wants to catch "layering" — the obfuscation stage where a launderer routes funds across a coordinated cohort of accounts so no single transfer trips the $10,000 reporting threshold. A path or rules query can find the rough shape (fan-in, fan-out, scatter-gather), but the signal that separates a real motif from a lookalike is a constraint that must hold *jointly* across whichever accounts and edges the detector picks — dollar conservation, distinct beneficial owners, a target sum, a KYC mix. The dataset is a shared ledger of 90 accounts and 138 transactions. The analysis runs three constraint-programming motif detectors over it.

```text
shared ledger: 90 accounts (beneficial owner, KYC tier, jurisdiction) · 138 transactions (amount, time)
      │
      ▼
/rai-prescriptive-problem   (three CSP motif detectors)
   • butterfly (scatter-gather): 1 source → 3 same-owner hubs → 1 dest, per-hub $ conservation, all sub-$10k
        -> 2 rings found (enumeration exhausted)
   • smurf army (fan-in): 5 distinct-owner accounts → 1 merchant, summing ~$27k within a 60-min window
        -> 5 cohorts (solution-limit cap hit; more exist)
   • KYC-mix burst (fan-in): 5 accounts → 1 flagged target within 60 min, at least 4 retail-tier
        -> cohorts surfaced (count depends on target scope + solution limit)
      │
      ▼
/rai-prescriptive-results
   • each motif is a joint constraint a rules/path query alone can't express; the planted decoys are correctly excluded
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the three motif detectors all read the shared `Account`/`Transaction` ledger the build step created. (In the template these are three runner scripts — `motif_butterfly.py`, `motif_smurf_army.py`, `motif_kyc_burst.py` — sharing `model_setup.py`.)

---

## 1. Build the ontology

**Prompt:** /rai-ontology Build an ontology from `data/accounts.csv` (each account has a beneficial-owner id, a KYC tier, and a jurisdiction) and `data/transactions.csv` (each transaction is a directed transfer from a source account to a destination account with a dollar amount and a timestamp in minutes). Model the transaction as a relationship from a source account to a destination account.

**Response:** Loads `Account` (90, with `bo_id` beneficial-owner cluster, `kyc_tier`, `jurisdiction`) and `Transaction` (138 directed transfers, each with `amount_dollars` and `ts_minutes`) — a transaction ledger with two planted scatter-gather rings, a smurf cohort, a KYC-burst cohort, decoys, and noise.

## 2. Examine the ontology

**Prompt:** /rai-pyrel What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** Two concepts — 90 `Account` (beneficial owner, KYC tier, jurisdiction) and 138 `Transaction` (directed transfers with amount and timestamp) — forming a directed money-flow graph. The CTR reporting threshold is $10,000; all motif transfers sit below it.

## 3. Detect butterfly (scatter-gather) rings

**Prompt:** /rai-prescriptive-problem Find butterfly scatter-gather rings: one source account that fans funds out to exactly 3 hub accounts sharing the same beneficial owner, which then gather into one destination account — with no direct source-to-destination or hub-to-hub edges, every transfer under $10,000, and each hub's dollars in roughly equal to its dollars out (flow conservation within 5%). Enumerate all such rings.

**Response:** OPTIMAL — enumeration exhausted (MiniZinc), **2 rings found**, both planted scatter-gathers: SourceShellCorp → 3 same-owner hubs → WireRecipientCorp, and SecondShellCorp → 3 same-owner hubs → OffshoreLLC (12 motif edges total). The per-hub dollar-conservation constraint is what rejects structurally-similar but non-laundering fan-outs.

## 4. Detect a smurf army (fan-in)

**Prompt:** /rai-prescriptive-problem Find smurf cohorts: exactly 5 accounts, each with a distinct beneficial owner, each sending a sub-$10,000 transfer into the same target merchant, where the transfers sum to about $27,000 and all fall within a 60-minute window. Enumerate the cohorts.

**Response:** SOLUTION_LIMIT — the solver hit its cap of 5 enumerated cohorts (more exist; raise the limit to see them). All five fan into the same merchant, sum to ~$27,000 within the window, and have pairwise-distinct beneficial owners. The distinct-owner constraint correctly prevents the two decoy accounts that share a beneficial owner from both appearing in one cohort.

## 5. Detect a KYC-mix burst (fan-in)

**Prompt:** /rai-prescriptive-problem Find KYC-mix bursts: exactly 5 accounts that each send a sub-$10,000 transfer into the same target within a 60-minute window, where at least 4 of the 5 are retail-tier accounts. Enumerate the cohorts.

**Response:** The detector returns KYC-burst cohorts — 5 sub-$10k transfers into one flagged target within the window, at least 4 from retail-tier accounts. The **at-least-4-retail cardinality over the chosen subset** is the joint condition a per-account rule can't capture. How many cohorts surface depends on how tightly the target and window are scoped (and the solution-limit cap): pinned to the planted target the shipped script surfaces a small set, while a looser target scope admits many more — so treat this motif as "find the bursts at this target," not a fixed count.

## Data

Bundled CSVs in `data/`: 90 accounts, 138 transactions (deterministically generated by `data/generate.py`, whose output ships with the template). The motif parameters (hub count, target sum, windows, KYC floor, solution limits) live in the runner scripts. Full models in `model_setup.py` plus the three `motif_*.py` runners.
