"""Transaction Screening (rules-based reasoning, local DuckDB) template.

This script demonstrates an anti-money-laundering triage in RelationalAI,
running entirely against an in-memory DuckDB database — no Snowflake account
or Native App required:

- Load a transfer ledger into DuckDB and model accounts over it.
- Define a self-referential `transfers_to` relationship between accounts.
- Author declarative rules as derived Relationships using `define()` + `where()`:
  structuring (transfers just under the reporting threshold), large sender,
  and a combined suspect flag.
- Expand a one-hop investigation set across the transfer network with a
  relationship self-join.

The whole pipeline is declarative — PyRel resolves dependencies automatically.

Run:
    `python transaction_screening_local.py`

Output:
    Prints the network overview, per-account sent volume, the suspect accounts,
    each suspect's transfer counterparties, and the full investigation set.
"""

from pathlib import Path

import relationalai.semantics as rai
from relationalai.config import DuckDBConnection, create_config
from relationalai.semantics import String
from relationalai.semantics.std import aggregates as aggs

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"

# Transfers just under the 10k reporting threshold count as structuring.
STRUCTURING_FLOOR, STRUCTURING_CEILING = 9000.0, 10000.0
LARGE_TRANSFER = 50000.0

# Local DuckDB config (no Snowflake): a duckdb connection plus a `deployment`
# section (schema + auto_deploy) routes the model to the local DuckDB executor
# and materializes derived relations before queries.
config = create_config(
    connections={"local": DuckDBConnection(path=":memory:")},  # or a file path, e.g. "./dev.duckdb"
    default_connection="local",
    deployment={"schema": "main", "auto_deploy": True},
)

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------
# Load the ledger straight into DuckDB. Keep source data in a schema (`raw`)
# separate from the model install schema (`main`) — DuckDB is case-insensitive,
# so a source table named like a concept would collide with the installed view.
session = config.get_connection(DuckDBConnection).get_session()
session.execute("CREATE SCHEMA IF NOT EXISTS raw")
session.execute(
    f"CREATE OR REPLACE TABLE raw.txn AS SELECT * FROM read_csv_auto('{DATA_DIR / 'transactions.csv'}')"
)

model = rai.Model("transaction_screening_local", config=config)
txn = model.Table("memory.raw.txn")  # 3-part FQN: <database>.<schema>.<table>

# Account concept: a party that sends or receives transfers.
Account = model.Concept("Account", identify_by={"id": String})
model.define(Account.new(id=txn.src), Account.new(id=txn.dst))

# transfers_to relationship: built with explicit two-ref binding. (The
# filter_by(id=col).rel(filter_by(id=col2)) shortcut produces self-loops here.)
Account.transfers_to = model.Relationship(f"{Account} transfers to {Account:other}")
_src, _dst = Account.ref(), Account.ref()
model.where(_src.id == txn.src, _dst.id == txn.dst).define(_src.transfers_to(_dst))

# --------------------------------------------------
# Stage 1: account classification rules
# --------------------------------------------------
# Structuring: sent a transfer in the just-under-threshold band.
Account.is_structuring = model.Relationship(f"{Account} is structuring")
model.where(
    txn.src == Account.id,
    txn.amount >= STRUCTURING_FLOOR,
    txn.amount < STRUCTURING_CEILING,
).define(Account.is_structuring())

# Large sender: sent a transfer above the large-transfer threshold.
Account.is_large_sender = model.Relationship(f"{Account} is large sender")
model.where(txn.src == Account.id, txn.amount > LARGE_TRANSFER).define(Account.is_large_sender())

# Suspect: structuring OR large sender (OR via two definitions).
Account.is_suspect = model.Relationship(f"{Account} is suspect")
model.where(Account.is_structuring()).define(Account.is_suspect())
model.where(Account.is_large_sender()).define(Account.is_suspect())

# --------------------------------------------------
# Stage 2: investigation expansion (one hop from a suspect)
# --------------------------------------------------
Account.near_suspect = model.Relationship(f"{Account} near suspect")
_other = Account.ref()
model.where(Account.transfers_to(_other), _other.is_suspect()).define(Account.near_suspect())
model.where(_other.transfers_to(Account), _other.is_suspect()).define(Account.near_suspect())

# --------------------------------------------------
# Results
# --------------------------------------------------
print("== Network overview ==")
model.select(
    aggs.count(txn.id).alias("transactions"),
    aggs.sum(txn.amount).alias("total_moved"),
).inspect()

print("\n== Sent volume per account ==")
model.where(txn.src == Account.id).select(
    Account.id.alias("account"),
    aggs.sum(txn.amount).per(Account).alias("total_sent"),
    aggs.count(txn.id).per(Account).alias("sent_count"),
).inspect()

print("\n== Suspect accounts (rules) ==")
model.where(Account.is_suspect()).select(Account.id.alias("suspect")).inspect()

print("\n== Suspect -> counterparty (relationship self-join) ==")
_counterparty = Account.ref()
model.where(Account.is_suspect(), Account.transfers_to(_counterparty)).select(
    Account.id.alias("suspect"),
    _counterparty.id.alias("counterparty"),
).inspect()

print("\n== Investigation set (suspect or one hop from a suspect) ==")
model.where(Account.near_suspect()).select(Account.id.alias("flagged_for_review")).inspect()
