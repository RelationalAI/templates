"""Assembly chains: every bottom-up chain that builds each finished good, which chains are maximal,
each chain's length, and each SKU's assembly depth."""

from relationalai.semantics import Hash, Integer, not_
from relationalai.semantics.std import aggregates as aggs

from .schema import SKU, BillOfMaterials, model

# --------------------------------------------------
# Assembly path enumeration
#   PREVIEW capability; requires relationalai>=1.15.
# --------------------------------------------------
# Where betweenness scores a single *node*, this enumerates the full *chains*
# that build each finished good: every bottom-up assembly path from a raw
# material up through its components to the finished good. We derive a binary
# SKU->SKU "feeds into" edge from the BillOfMaterials intermediary (the input
# SKU feeds the output SKU), enumerate all such paths, then mark the
# maximal (non-extendable) chains so that sub-paths can be suppressed.

# Binary SKU->SKU edge: input_sku "feeds into" output_sku. This is the
# build-direction (bottom-up) reverse of the depends-on graph edge above.
SKU.feeds = model.Relationship(f"{SKU} feeds into {SKU}", short_name="feeds")
bom_ref = BillOfMaterials.ref()
sku_in, sku_out = SKU.ref(), SKU.ref()
model.where(
    bom_ref.input_sku(sku_in),
    bom_ref.output_sku(sku_out),
).define(sku_in.feeds(sku_out))

# Enumerate every assembly chain. The BOM is a DAG (raw materials -> components
# -> finished goods, never back), so .all().paths() already yields simple paths --
# there is no cycle risk, and the repeat bound only needs to cover the BOM depth.
# Deepest chain here is raw_material -> component -> finished_good (2 hops); we
# allow extra headroom so deeper BOMs enumerate fully.
MAX_ASSEMBLY_HOPS = 4
p = model.path(SKU.feeds.repeat(1, MAX_ASSEMBLY_HOPS)).all().paths()

# The chains, which the deployed model publishes for the queries: the SKU at each step of
# each chain, keyed by the chain's path id.
AssemblyStep = model.Relationship(
    f"assembly chain {Hash:path} has {SKU:sku} at step {Integer:step}"
)
model.where(p).define(AssemblyStep(p, SKU(p.nodes), p.nodes["index"]))

# A chain is maximal when nothing feeds its first SKU and its last SKU feeds nothing.
# A chain longer than MAX_ASSEMBLY_HOPS is not enumerated, so it is never marked maximal.
MaximalChain = model.Relationship(f"assembly chain {Hash:path} is maximal")
first, last, upstream, downstream = SKU.ref(), SKU.ref(), SKU.ref(), SKU.ref()
model.where(
    p,
    p.nodes(0) == first,
    p.nodes(p.length) == last,
    not_(upstream.feeds(first)),
    not_(last.feeds(downstream)),
).define(MaximalChain(p))

# A finished SKU reached by a chain longer than MAX_ASSEMBLY_HOPS: the chain's last
# MAX_ASSEMBLY_HOPS hops are enumerated, and something feeds their first SKU.
end = SKU.ref()
SKU.exceeds_hop_bound = model.Relationship(f"{SKU} ends an assembly chain longer than the hop bound")
model.where(
    p,
    p.length == MAX_ASSEMBLY_HOPS,
    p.nodes(0) == first,
    p.nodes(p.length) == end,
    upstream.feeds(first),
    not_(end.feeds(downstream)),
).define(end.exceeds_hop_bound())

# Assembly depth of each SKU that ends a maximal chain: the length of the longest one.
# A SKU whose deepest chain exceeds the bound gets no depth rather than an understated one.
SKU.assembly_depth = model.Property(f"{SKU} has assembly depth {Integer:assembly_depth}")
model.where(MaximalChain(p), p.nodes(p.length) == end, not_(end.exceeds_hop_bound())).define(
    end.assembly_depth(aggs.max(p.length).per(end))
)

# Each chain's length in hops.
ChainLength = model.Relationship(f"assembly chain {Hash:path} has {Integer:hops} hops")
model.where(p).define(ChainLength(p, p.length))
