# Transaction Screening (Local DuckDB) — Runbook

A paste-testable walkthrough for an analyst. Each prompt below is something you paste into a RelationalAI agent session; the Response is what the agent should produce against this ontology. Most of the ledger is legitimate traffic; the suspect subgraph is small and legible, so the flagged counts stay checkable by hand.

**The problem.** An anti-money-laundering analyst has a transfer ledger (75 transfers, 54 accounts) and needs to decide which accounts to investigate. As in real AML, only a small minority of accounts are suspicious — here 6 of 54 (about 11%) flag. The chain classifies accounts that move money just under the reporting threshold, flags large senders, and expands the review set to everyone who transacted with a flagged account — all on a local DuckDB database, no Snowflake.

```
transactions.csv — 75 transfers, 54 accounts  (in-memory DuckDB, no Snowflake)
        │
        ▼  /rai-setup and /rai-pyrel  — ontology
        Account · transfers_to (self-referential)
        │
        ▼  /rai-pyrel  — classification
        is_structuring · is_large_sender · is_suspect · near_suspect · under_review
        → 6 suspects
        │
        ▼  /rai-pyrel  — surface and expand
        suspect → counterparty (self-join) · investigation set
        → 8 accounts under review
```

**These prompts are designed to run in order, in a single session** — each builds on the ontology state created by the ones before it.

Requires `relationalai >= 1.13`. Local DuckDB execution uses deploy mode (flagged experimental in the package).

---

## Setup

### Build the model

> Set up a RelationalAI model on local DuckDB (no Snowflake) over `data/transactions.csv` (columns: `id, src, dst, amount`). Create an `Account` concept identified by `id`, drawn from both the `src` and `dst` of every transfer, and a self-referential `transfers_to` relationship linking each transfer's sender to its receiver.

**Response.** A model on an in-memory DuckDB database, configured with a `deployment` section (`schema` and `auto_deploy`). `Account` has 54 instances; `transfers_to` has 75 directed links, one per transfer. (To count the links, count the transfers — `aggs.count(<transfer id>)`. Counting a single account ref instead collapses to distinct senders, not arcs.)

### Examine the ontology

> What concepts and relationships does the model have, and how much money does the ledger move?

**Response.** `Account` has 54 instances, linked by a self-referential `transfers_to` (75 links, one per transfer). The ledger holds 75 transfers totalling 870,000. (The exact concept inventory is a modeling choice — e.g. transfers may be a relationship or a `Transfer` row entity; the counts above are what matters.)

---

## Analyst questions

### Which accounts are suspect?

> Flag the accounts worth a closer look. Treat an account as **structuring** if it sent any transfer of at least 9,000 and under 10,000 (just under the 10,000 reporting threshold), and a **large sender** if it sent any transfer over 50,000. An account is a **suspect** if either holds. Which accounts are suspect?

**Response.** 6 suspects out of 54 accounts: `C1001` (large sender — a single 60,000 transfer) and `C2001`–`C2005` (each structuring, with transfers of 9,400–9,900). Every other account — including the `C3xxx` legitimate-traffic network — is clean. The thresholds are sharp edges: near-miss transfers of 8,900, exactly 10,000, 49,000, and exactly 50,000 all sit just outside the bands and correctly do not flag their senders.

### Who did the suspects transfer to?

> For each suspect, which accounts did they transfer money to?

**Response.** 8 suspect-to-counterparty pairs: `C1001` to `C1002`, `C1001` to `C1003`, and the ring `C2001` to `C2002`, `C2001` to `C2003`, `C2002` to `C2003`, `C2003` to `C2004`, `C2004` to `C2005`, `C2005` to `C2001`. The accounts `C2001` through `C2005` form the structuring ring.

### Who is in the investigation set?

> Build the investigation set: every account that is itself a suspect or transacted directly with a suspect, in either direction. Who should we pull files on?

**Response.** 8 accounts under review out of 54: the 6 suspects (`C1001`, `C2001`–`C2005`) plus `C1002` and `C1003`, which received transfers from the large sender `C1001`. The ring members are all in the set because they transact with one another. Note the expansion is one hop from a *suspect*, not transitive: `C1004` received from `C1003`, but `C1003` is not a suspect, so `C1004` stays out — and the entire `C3xxx` legitimate network stays out too.

---

## Cohesion

Every number above matches the script's printed output (`transaction_screening_local.py`): 75 transfers and 870,000 moved; 6 suspects (of 54 accounts); 8 suspect-to-counterparty pairs; 8 accounts in the investigation set. Re-run the script to refresh these if the data or thresholds change.
