"""Review queue: the accumulation picture if every review-band pair were confirmed. Records
re-cluster over the accepted and review edges, each confirmed party's exposure is totaled, and the
parties over the accumulation limit are counted against those auto-resolution finds."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

from .resolved_parties import ACCUMULATION_LIMIT, num_party_breaches
from .schema import CandidateMatch, Record, ReviewPair, model

# Weakly connected components over the accepted and the review-band pairs.
review_graph = Graph(
    model, directed=False, weighted=False, node_concept=Record, name="review_graph"
)
_match, _review = CandidateMatch.ref(), ReviewPair.ref()
_rec_a, _rec_b = Record.ref(), Record.ref()
model.where(_match.rec_a == _rec_a, _match.rec_b == _rec_b).define(
    review_graph.Edge.new(src=_rec_a, dst=_rec_b)
)
model.where(_review.rec_a == _rec_a, _review.rec_b == _rec_b).define(
    review_graph.Edge.new(src=_rec_a, dst=_rec_b)
)
review_graph.Node.confirmed_id = review_graph.weakly_connected_component()

# Each record's confirmed party key is its component's representative record id.
Record.confirmed_key = model.Property(f"{Record} has confirmed party key {Integer:confirmed_key}")
_rep_node = Record.ref()
model.where(Record.confirmed_id == _rep_node).define(Record.confirmed_key(_rep_node.record_id))

# The parties confirming the review queue would resolve, and their total exposure.
ConfirmedParty = model.Concept("ConfirmedParty", identify_by={"key": Integer})
ConfirmedParty.total_exposure = model.Property(f"{ConfirmedParty} has {Float:total_exposure}")
model.define(ConfirmedParty.new(key=Record.confirmed_key))
_member = Record.ref()
model.where(_member.confirmed_key == ConfirmedParty.key).define(
    ConfirmedParty.total_exposure(aggs.sum(_member, _member.coverage_amount).per(ConfirmedParty))
)

# Confirmed parties over the accumulation limit, and how many of them auto-resolution misses.
num_confirmed_breaches = model.Relationship(
    f"confirming the review queue gives {Integer:n_parties} parties over the accumulation limit"
)
num_surfaced_breaches = model.Relationship(
    f"confirming the review queue surfaces {Integer:n_parties} breached parties that resolution "
    "misses"
)
model.define(
    num_confirmed_breaches(
        aggs.count(ConfirmedParty).where(ConfirmedParty.total_exposure > ACCUMULATION_LIMIT) | 0
    )
)
_confirmed, _resolved = Integer.ref(), Integer.ref()
model.where(num_confirmed_breaches(_confirmed), num_party_breaches(_resolved)).define(
    num_surfaced_breaches(_confirmed - _resolved)
)
