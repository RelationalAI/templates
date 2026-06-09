# Transaction Screening (Local DuckDB) — Runbook

A paste-testable walkthrough for an analyst. Each prompt below is something you paste into a RelationalAI agent session; the Response is what the agent should produce against this ontology. The dataset is small and legible so every number is checkable.

**The problem.** An anti-money-laundering analyst has a transfer ledger (10 transfers, 9 accounts) and needs to decide which accounts to investigate. The chain classifies accounts that move money just under the reporting threshold, flags large senders, and expands the review set to everyone who transacted with a flagged account — all on a local DuckDB database, no Snowflake.

```
transactions.csv — 10 transfers, 9 accounts  (in-memory DuckDB, no Snowflake)
        │
        ▼  /rai-setup + /rai-pyrel-coding  — ontology
        Account · transfers_to (self-referential)
        │
        ▼  /rai-rules-authoring  — classification
        is_structuring · is_large_sender · is_suspect · near_suspect · under_review
        → 6 suspects
        │
        ▼  /rai-querying  — surface & expand
        suspect → counterparty (self-join) · investigation set
        → 8 accounts under review
```

**These prompts are designed to run in order, in a single session** — each builds on the ontology state created by the ones before it.

Requires `relationalai >= 1.11`. Local DuckDB execution uses deploy mode (flagged experimental in the package).

---

## Setup

### Build the model

> Set up a RelationalAI model on local DuckDB (no Snowflake) over `data/transactions.csv` (columns: `id, src, dst, amount`). Create an `Account` concept identified by `id`, drawn from both the `src` and `dst` of every transfer, and a self-referential `transfers_to` relationship linking each transfer's sender to its receiver.

**Response.** A model on an in-memory DuckDB database, configured with a `deployment` section (`schema` + `auto_deploy`). `Account` has 9 instances; `transfers_to` has 10 directed links, one per transfer.

### Examine the ontology

> What concepts and relationships does the model have, and how much money does the ledger move?

**Response.** `Account` has 9 instances, linked by a self-referential `transfers_to` (10 links, one per transfer). The ledger holds 10 transfers totalling 142,900. (The exact concept inventory is a modeling choice — e.g. transfers may be a relationship or a `Transfer` row entity; the counts above are what matters.)

---

## Analyst questions

### Which accounts are suspect?

> Flag the accounts worth a closer look. Treat an account as **structuring** if it sent any transfer of at least 9,000 and under 10,000 (just under the 10,000 reporting threshold), and a **large sender** if it sent any transfer over 50,000. An account is a **suspect** if either holds. Which accounts are suspect?

**Response.** 6 suspects: `C1001` (large sender — a single 60,000 transfer) and `C2001`–`C2005` (each structuring, with transfers of 9,400–9,900). Accounts `C1002`, `C1003`, `C1004` are clean.

### Who did the suspects transfer to?

> For each suspect, which accounts did they transfer money to?

**Response.** 8 suspect → counterparty pairs: `C1001`→`C1002`, `C1001`→`C1003`, and the ring `C2001`→`C2002`, `C2001`→`C2003`, `C2002`→`C2003`, `C2003`→`C2004`, `C2004`→`C2005`, `C2005`→`C2001`. The `C2001`–`C2005` cycle is the structuring ring.

### Who is in the investigation set?

> Build the investigation set: every account that is itself a suspect or transacted directly with a suspect, in either direction. Who should we pull files on?

**Response.** 8 accounts under review: the 6 suspects (`C1001`, `C2001`–`C2005`) plus `C1002` and `C1003`, which received transfers from the large sender `C1001`. The ring members are all in the set because they transact with one another.

---

## Cohesion

Every number above matches the script's printed output (`transaction_screening_local.py`): 10 transfers / 142,900 moved; 6 suspects; 8 suspect→counterparty pairs; 8 accounts in the investigation set. Re-run the script to refresh these if the data or thresholds change.
