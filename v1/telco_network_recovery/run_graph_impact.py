"""Compute PageRank and per-tower customer impact from deployed ontology tables.

Inputs:
  BERTOLANI.TELCO_NETWORK_RECOVERY.{SUBSCRIBER, CALLDETAILRECORD, CELLTOWER}

Outputs:
  BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.SUBSCRIBER_INFLUENCE
  BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.TOWER_CUSTOMER_IMPACT
"""

from relationalai.semantics import Float, Integer, Model, distinct
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

from deployed_ontology import bind_graph_base, table_sources
from reasoner_common import replace_table


def build_model():
    model = Model("Telco Graph Impact From Deployed Tables")
    ontology = bind_graph_base(
        model,
        table_sources(
            model,
            [
                "CELLTOWER",
                "SUBSCRIBER",
                "CALLDETAILRECORD",
            ],
        ),
    )
    CellTower = ontology.CellTower
    Subscriber = ontology.Subscriber
    CallDetailRecord = ontology.CallDetailRecord

    call_graph = Graph(
        model,
        directed=True,
        weighted=False,
        node_concept=Subscriber,
        aggregator="sum",
    )
    cdr = CallDetailRecord.ref()
    caller = Subscriber.ref()
    callee = Subscriber.ref()
    model.where(
        cdr.caller(caller),
        cdr.callee(callee),
    ).define(call_graph.Edge.new(src=caller, dst=callee))
    call_graph.Node.influence_score = call_graph.pagerank()

    CellTower.impact_count = model.Property(f"{CellTower} has {Integer:impact_count}")
    CellTower.weighted_impact = model.Property(
        f"{CellTower} has {Float:weighted_impact}"
    )
    CellTower.weighted_pagerank = model.Property(
        f"{CellTower} has {Float:weighted_pagerank}"
    )

    model.define(
        CellTower.impact_count(
            aggs.count(distinct(Subscriber))
            .where(
                CallDetailRecord.routed_through(CellTower),
                CallDetailRecord.caller(Subscriber),
                Subscriber.status == "ACTIVE",
            )
            .per(CellTower)
        )
    )
    model.define(
        CellTower.weighted_impact(
            aggs.sum(Subscriber.customer_value)
            .where(
                CallDetailRecord.routed_through(CellTower),
                CallDetailRecord.caller(Subscriber),
                Subscriber.status == "ACTIVE",
            )
            .per(CellTower)
        )
    )
    model.define(
        CellTower.weighted_pagerank(
            aggs.sum(Subscriber.influence_score)
            .where(
                CallDetailRecord.routed_through(CellTower),
                CallDetailRecord.caller(Subscriber),
                Subscriber.status == "ACTIVE",
            )
            .per(CellTower)
        )
    )
    return model, CellTower, Subscriber


def main():
    model, CellTower, Subscriber = build_model()

    subscriber_scores = model.select(
        Subscriber.id.alias("SUBSCRIBER_ID"),
        Subscriber.influence_score.alias("INFLUENCE_SCORE"),
    ).to_df()
    subscriber_scores["INFLUENCE_SCORE"] = subscriber_scores[
        "INFLUENCE_SCORE"
    ].astype(float)
    replace_table(subscriber_scores, "SUBSCRIBER_INFLUENCE")

    tower_impact = (
        model.where(CellTower.impact_count)
        .select(
            CellTower.id.alias("TOWER_ID"),
            CellTower.impact_count.alias("IMPACT_COUNT"),
            CellTower.weighted_impact.alias("WEIGHTED_IMPACT"),
            CellTower.weighted_pagerank.alias("WEIGHTED_PAGERANK"),
        )
        .to_df()
    )
    tower_impact["IMPACT_COUNT"] = tower_impact["IMPACT_COUNT"].astype("int64")
    tower_impact["WEIGHTED_IMPACT"] = tower_impact["WEIGHTED_IMPACT"].astype(float)
    tower_impact["WEIGHTED_PAGERANK"] = tower_impact["WEIGHTED_PAGERANK"].astype(float)
    replace_table(tower_impact, "TOWER_CUSTOMER_IMPACT")


if __name__ == "__main__":
    main()
