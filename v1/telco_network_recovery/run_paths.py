"""Trace high-influence call paths from deployed tables and PageRank output.

Inputs:
  BERTOLANI.TELCO_NETWORK_RECOVERY.CALLDETAILRECORD
  BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.SUBSCRIBER_INFLUENCE

Output:
  BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.TOP_CALL_PATH
"""

import pandas as pd
from relationalai.semantics import Float, Integer, Model, not_, where
from relationalai.semantics.std import aggregates as aggs

from deployed_ontology import bind_graph_base, table_sources
from reasoner_common import RESULTS_SCHEMA, replace_table, table

PATH_MAX_HOPS = 3


def empty_output():
    return pd.DataFrame(
        columns=[
            "HUB_SUBSCRIBER_ID",
            "INFLUENCE_LOAD",
            "SUBSCRIBER_PATH",
            "TOWER_PATH",
        ]
    )


def build_model():
    model = Model("Telco Paths From Deployed Tables")
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

    influence_src = model.Table(table("SUBSCRIBER_INFLUENCE", RESULTS_SCHEMA))
    Subscriber.influence_score = model.Property(
        f"{Subscriber} has {Float:influence_score}"
    )
    model.define(
        Subscriber.lookup(id=influence_src.SUBSCRIBER_ID).influence_score(
            influence_src.INFLUENCE_SCORE
        )
    )

    Subscriber.calls_via = model.Relationship(
        f"{Subscriber:caller} via {CellTower:tower} calls {Subscriber:callee}"
    )
    cdr = CallDetailRecord.ref()
    caller_sub = Subscriber.ref()
    callee_sub = Subscriber.ref()
    via_tower = CellTower.ref()
    model.where(
        cdr.caller(caller_sub),
        cdr.callee(callee_sub),
        cdr.routed_through(via_tower),
    ).define(caller_sub.calls_via(via_tower, callee_sub))

    return model, CellTower, Subscriber


def find_top_path(model, CellTower, Subscriber):
    influence = model.select(
        Subscriber.id.alias("SUBSCRIBER_ID"),
        Subscriber.influence_score.alias("INFLUENCE_SCORE"),
    ).to_df()
    if influence.empty:
        return empty_output()

    influence["SUBSCRIBER_ID"] = influence["SUBSCRIBER_ID"].astype(str)
    influence["INFLUENCE_SCORE"] = influence["INFLUENCE_SCORE"].astype(float)
    hub_id = (
        influence.sort_values(
            ["INFLUENCE_SCORE", "SUBSCRIBER_ID"], ascending=[False, True]
        )
        .iloc[0]["SUBSCRIBER_ID"]
    )

    seed = Subscriber.ref()
    i = Integer.ref()
    j = Integer.ref()
    p = model.path(seed, Subscriber.calls_via.repeat(1, PATH_MAX_HOPS)).all().paths()
    score_df = model.where(
        seed.id == hub_id,
        p,
        not_(where(i < j, p.nodes(i) == p.nodes(j))),
        total := aggs.sum(Subscriber(p.nodes).influence_score).per(p),
    ).select(
        p.alias("PATH_ID"),
        total.alias("INFLUENCE_LOAD"),
    ).to_df()
    if score_df.empty:
        return empty_output()

    score_df["INFLUENCE_LOAD"] = score_df["INFLUENCE_LOAD"].astype(float)
    simple_path_ids = set(score_df["PATH_ID"])

    seed_n = Subscriber.ref()
    p_nodes = model.where(
        seed_n.id == hub_id,
        pn := model.path(
            seed_n, Subscriber.calls_via.repeat(1, PATH_MAX_HOPS)
        ).all().paths(),
    ).select(
        pn.alias("PATH_ID"),
        pn.nodes["index"].alias("STEP"),
        Subscriber(pn.nodes).id.alias("SUBSCRIBER_ID"),
    ).to_df()
    p_nodes["STEP"] = p_nodes["STEP"].astype(int)
    p_nodes = p_nodes[p_nodes["PATH_ID"].isin(simple_path_ids)]

    seed_h = Subscriber.ref()
    p_hops = model.where(
        seed_h.id == hub_id,
        ph := model.path(
            seed_h, Subscriber.calls_via.repeat(1, PATH_MAX_HOPS)
        ).all().paths(),
    ).select(
        ph.alias("PATH_ID"),
        ph.relationship_fields["index"].alias("HOP"),
        ph.relationship_fields["field_index"].alias("FIELD_INDEX"),
        CellTower(ph.relationship_fields["field"]).id.alias("TOWER_ID"),
    ).to_df()
    if not p_hops.empty:
        p_hops = p_hops[p_hops["FIELD_INDEX"].astype(int) == 1]
        p_hops["HOP"] = p_hops["HOP"].astype(int)
        p_hops = p_hops[p_hops["PATH_ID"].isin(simple_path_ids)]

    subscriber_path_by_id = {
        path_id: " -> ".join(group.sort_values("STEP")["SUBSCRIBER_ID"].tolist())
        for path_id, group in p_nodes.groupby("PATH_ID")
    }
    tower_path_by_id = {}
    if not p_hops.empty:
        tower_path_by_id = {
            path_id: " -> ".join(group.sort_values("HOP")["TOWER_ID"].tolist())
            for path_id, group in p_hops.groupby("PATH_ID")
        }

    top_row = score_df.sort_values(
        ["INFLUENCE_LOAD", "PATH_ID"], ascending=[False, True]
    ).iloc[0]
    top_path_id = top_row["PATH_ID"]
    return pd.DataFrame(
        [
            {
                "HUB_SUBSCRIBER_ID": hub_id,
                "INFLUENCE_LOAD": float(top_row["INFLUENCE_LOAD"]),
                "SUBSCRIBER_PATH": subscriber_path_by_id.get(top_path_id, ""),
                "TOWER_PATH": tower_path_by_id.get(top_path_id, ""),
            }
        ]
    )


def main():
    model, CellTower, Subscriber = build_model()
    replace_table(find_top_path(model, CellTower, Subscriber), "TOP_CALL_PATH")


if __name__ == "__main__":
    main()
