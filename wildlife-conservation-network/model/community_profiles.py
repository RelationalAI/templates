"""Community profiles: each Louvain community's size, member order, hub organization, primary
region, and the ranked regions, species focuses, and organization types of its members."""

from relationalai.semantics import Integer, String
from relationalai.semantics.std import aggregates as aggs

# Declares Organization.community and Organization.degree_centrality, the graph results read here.
from . import partnership_network  # noqa: F401
from .schema import Organization, model

# --------------------------------------------------
# Communities, their members, and their hubs
# --------------------------------------------------

# One Community per Louvain community id.
Community = model.Concept("Community", identify_by={"id": Integer})
model.define(Community.new(id=Organization.community))

Community.n_organizations = model.Property(
    f"{Community} has {Integer:n_organizations} organizations"
)
model.define(
    Community.n_organizations(
        aggs.count(Organization).per(Community).where(Organization.community == Community.id)
    )
)

# Member order within a community: highest degree centrality first, ties broken by the lower
# organization id. The centrality is negated so both keys sort ascending.
Community.member = model.Relationship(
    f"{Community} has {Organization:org} at member rank {Integer:member_rank}"
)
model.where(Organization.community == Community.id).define(
    Community.member(
        Organization,
        aggs.rank(-Organization.degree_centrality, Organization.id).per(Community),
    )
)

# The hub is the top-ranked member: the organization best placed to coordinate its community.
Community.hub = model.Property(f"{Community} has hub {Organization:hub}")
_member_rank = Integer.ref()
model.where(Community.member(Organization, _member_rank), _member_rank == 1).define(
    Community.hub(Organization)
)

# --------------------------------------------------
# Region, species focus, and organization types
# --------------------------------------------------

# One CommunityTrait per value of a trait among a community's members. The kind is `region`,
# `species` (focus species), or `type` (organization type).
CommunityTrait = model.Concept(
    "CommunityTrait",
    identify_by={"community": Community, "kind": String, "value": String},
)
CommunityTrait.n_organizations = model.Property(
    f"{CommunityTrait} is held by {Integer:n_organizations} organizations"
)
# The member rank of the most central organization holding the value.
CommunityTrait.first_member_rank = model.Property(
    f"{CommunityTrait} is first held at member rank {Integer:first_member_rank}"
)
# Order among the community's values of the same kind: most organizations first; a tie goes to
# the value held by the more central member. The count is negated so both keys sort ascending.
CommunityTrait.rank = model.Property(f"{CommunityTrait} has trait rank {Integer:rank}")

for kind, trait in (
    ("region", Organization.region),
    ("species", Organization.focus_species),
    ("type", Organization.type),
):
    holders = (
        Community.member(Organization, _member_rank),
        CommunityTrait.community == Community,
        CommunityTrait.kind == kind,
        CommunityTrait.value == trait,
    )
    model.where(Community.member(Organization, _member_rank)).define(
        CommunityTrait.new(community=Community, kind=kind, value=trait)
    )
    model.define(
        CommunityTrait.n_organizations(aggs.count(Organization).per(CommunityTrait).where(*holders))
    )
    model.define(
        CommunityTrait.first_member_rank(aggs.min(_member_rank).per(CommunityTrait).where(*holders))
    )

model.define(
    CommunityTrait.rank(
        aggs.rank(
            -CommunityTrait.n_organizations, CommunityTrait.first_member_rank
        ).per(CommunityTrait.community, CommunityTrait.kind)
    )
)

# The primary region is the top-ranked region.
Community.primary_region = model.Property(f"{Community} has primary region {String:primary_region}")
model.where(
    CommunityTrait.community == Community,
    CommunityTrait.kind == "region",
    CommunityTrait.rank == 1,
).define(Community.primary_region(CommunityTrait.value))
