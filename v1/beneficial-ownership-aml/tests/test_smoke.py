"""Phase 0 smoke test: one tiny ownership model on each backend.

Checks a supertype with identify_by, subtypes, a ternary Property, a derived
rule (direct majority control, P3 Rule 5) and a query.
"""

import uuid

import pytest
from relationalai.semantics import Float, Model, String


def _build_and_query(config):
    name = f"bo_smoke_{uuid.uuid4().hex[:8]}"
    model = Model(name, config=config) if config is not None else Model(name)

    Entity = model.Concept("Entity", identify_by={"eid": String})
    Company = model.Concept("Company", extends=[Entity])
    Person = model.Concept("Person", extends=[Entity])
    Entity.owns = model.Property(f"{Entity:owner} owns {Company:owned} with {Float:share}")
    Entity.controls = model.Relationship(f"{Entity:controller} controls {Entity:controlled}")

    companies = model.data([{"eid": "C:C"}, {"eid": "C:D"}])
    persons = model.data([{"eid": "P:P1"}])
    model.define(Company.new(companies.to_schema()))
    model.define(Person.new(persons.to_schema()))

    holdings = model.data([
        {"owner_eid": "P:P1", "owned_eid": "C:C", "share": 0.8},
        {"owner_eid": "C:C", "owned_eid": "C:D", "share": 0.4},
    ])
    model.where(
        o := Entity.lookup(eid=holdings.owner_eid),
        c := Company.lookup(eid=holdings.owned_eid),
    ).define(o.owns(c, holdings.share))

    x, y, w = Entity.ref(), Company.ref(), Float.ref()
    model.where(x.owns(y, w), w > 0.5).define(x.controls(y))

    a, b = Entity.ref(), Entity.ref()
    df = model.where(a.controls(b)).select(
        a.eid.alias("controller"), b.eid.alias("controlled")
    ).to_df()
    return sorted(map(tuple, df[["controller", "controlled"]].values.tolist()))


@pytest.mark.offline
def test_smoke_offline(offline_cfg):
    assert _build_and_query(offline_cfg) == [("P:P1", "C:C")]


@pytest.mark.snowflake
def test_smoke_snowflake(snowflake_cfg):
    assert _build_and_query(None) == [("P:P1", "C:C")]
