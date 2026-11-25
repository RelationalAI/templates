"""Resolved parties: one party per cluster of matched records, the records and golden record it
holds, its total exposure to the carrier, whether it breaches the accumulation limit, and the excess
and reinsurance premium of a breach."""

from relationalai.semantics import Integer
from relationalai.semantics.std import aggregates as aggs

# Declares Record.entity_key, the party key each record resolves to.
from . import match_graph  # noqa: F401
from .schema import Record, ResolvedParty, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

ACCUMULATION_LIMIT = 1_000_000.0
REINSURANCE_RATE = 0.12

# --------------------------------------------------
# Resolved membership, exposure, and breaches
# --------------------------------------------------

model.define(ResolvedParty.new(key=Record.entity_key))
record, party = Record.ref(), ResolvedParty.ref()
model.where(record.entity_key == party.key).define(
    record.resolved_party(party)
)

party_record = Record.ref()
model.where(party_record.entity_key == ResolvedParty.key).define(
    ResolvedParty.total_exposure(
        aggs.sum(party_record, party_record.coverage_amount).per(ResolvedParty)
    )
)
model.define(ResolvedParty.is_over_limit(ResolvedParty)).where(
    ResolvedParty.total_exposure > ACCUMULATION_LIMIT
)
model.where(ResolvedParty.total_exposure > ACCUMULATION_LIMIT).define(
    ResolvedParty.excess(
        ResolvedParty.total_exposure - ACCUMULATION_LIMIT
    )
)
model.define(
    ResolvedParty.premium(ResolvedParty.excess * REINSURANCE_RATE)
)

# --------------------------------------------------
# Party size and golden record
# --------------------------------------------------

# Records per party; a party with more than one record is multi-record, and each of its
# records is a duplicate.
ResolvedParty.n_records = model.Property(f"{ResolvedParty} has {Integer:n_records} records")
_member = Record.ref()
model.where(_member.entity_key == ResolvedParty.key).define(
    ResolvedParty.n_records(aggs.count(_member).per(ResolvedParty))
)
ResolvedParty.is_multi_record = model.Relationship(f"{ResolvedParty} holds more than one record")
model.where(ResolvedParty.n_records > 1).define(ResolvedParty.is_multi_record())
model.where(
    Record.resolved_party(ResolvedParty), ResolvedParty.is_multi_record(),
).define(Record.is_duplicate())

# The golden record is the party's latest record by creation date (ISO dates sort as text), the
# higher record id breaking a tie.
ResolvedParty.golden_record = model.Relationship(
    f"{ResolvedParty} has golden {Record:golden_record}"
)
model.where(
    _member.entity_key == ResolvedParty.key,
    aggs.rank_desc(_member.created_at, _member.record_id).per(ResolvedParty) == 1,
).define(ResolvedParty.golden_record(_member))

# --------------------------------------------------
# Counts the report prints
# --------------------------------------------------

num_parties = model.Relationship(f"the records resolve into {Integer:n_parties} parties")
num_record_breaches = model.Relationship(
    f"the records include {Integer:n_records} over the accumulation limit"
)
num_party_breaches = model.Relationship(
    f"the resolved parties include {Integer:n_parties} over the accumulation limit"
)
model.define(
    num_parties(aggs.count(ResolvedParty) | 0),
    num_record_breaches(aggs.count(Record).where(Record.coverage_amount > ACCUMULATION_LIMIT) | 0),
    num_party_breaches(aggs.count(ResolvedParty).where(ResolvedParty.is_over_limit()) | 0),
)
