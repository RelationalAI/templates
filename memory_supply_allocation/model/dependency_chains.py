"""Dependency chains: every 1-3 hop customer-customer dependency chain, each chain read as a route of
customer names, and the number of chains."""

from relationalai.semantics import Integer, String
from relationalai.semantics.std import aggregates
from relationalai.semantics.std.path import PathTraversal

# Declares Customer.depends_on, the edge the chains follow.
from . import customer_dependencies  # noqa: F401
from .schema import Customer, model

# --------------------------------------------------
# Stage 4: Graph (PATHS) -- dependency chains
# --------------------------------------------------
# Every 1-3 hop customer-customer dependency chain. The enumeration is declared
# here, in the model: a deployed model only has the path tables its own rules
# ask for. Each chain's customers are published with their step index.
chain = model.path(Customer.depends_on.repeat(1, 3)).all().paths()
DependencyChainStep = model.Relationship(
    f"{PathTraversal:chain} of {Integer:hops} hops visits {Customer} at step {Integer:step}"
)
model.where(chain).define(
    DependencyChainStep(chain, chain.length, Customer(chain.nodes), chain.nodes["index"])
)

# Each chain read as its customers' names in step order, "A -> B -> C".
DependencyChain = model.Relationship(
    f"{PathTraversal:chain} of {Integer:hops} hops reads {String:route}"
)
_hops, _step, _stop = Integer.ref(), Integer.ref(), Customer.ref()
model.where(chain).define(
    DependencyChain(
        chain,
        chain.length,
        aggregates.string_join(_stop.name, sep=" -> ", index=_step)
        .per(chain)
        .where(DependencyChainStep(chain, _hops, _stop, _step)),
    )
)

# The number of chains.
NumDependencyChains = model.Relationship(f"there are {Integer:num_chains} dependency chains")
_counted, _route = PathTraversal.ref(), String.ref()
model.define(
    NumDependencyChains(aggregates.count(_counted).where(DependencyChain(_counted, _hops, _route)))
)
