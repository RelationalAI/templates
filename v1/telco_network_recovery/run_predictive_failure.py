"""Train equipment-failure GNN from deployed ontology tables.

Inputs:
  BERTOLANI.TELCO_NETWORK_RECOVERY.{CELLTOWER, NETWORKEQUIPMENT,
  EQUIPMENTHEALTH, MODELADVISORY}

Output:
  BERTOLANI.TELCO_NETWORK_RECOVERY_RESULTS.TOWER_FAILURE_SCORE
"""

import pandas as pd
from relationalai.semantics import Any, Model, select
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

from deployed_ontology import bind_predictive_base, dataframe_sources
from reasoner_common import EXP_DATABASE, EXP_SCHEMA, replace_table, snowflake_connection, table

SEED = 42
GNN_EPOCHS = 80
GNN_LR = 0.002


def equipment_splits():
    conn = snowflake_connection()
    try:
        equipment_df = pd.read_sql(
            f"SELECT ID, STATUS FROM {table('NETWORKEQUIPMENT')}",
            conn,
        )
    finally:
        conn.close()

    equipment_df["AT_RISK"] = (
        equipment_df["STATUS"].isin(["FAILING", "WARNING"]).astype(int)
    )
    shuffled = equipment_df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    n = len(shuffled)
    train_n = int(n * 0.70)
    val_n = int(n * 0.15)
    train_df = shuffled.iloc[:train_n][["ID", "AT_RISK"]].rename(
        columns={"ID": "equipment_id", "AT_RISK": "at_risk"}
    )
    val_df = shuffled.iloc[train_n:train_n + val_n][["ID", "AT_RISK"]].rename(
        columns={"ID": "equipment_id", "AT_RISK": "at_risk"}
    )
    test_df = equipment_df[["ID"]].rename(columns={"ID": "equipment_id"})
    return equipment_df, train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


def deployed_inputs():
    conn = snowflake_connection()
    try:
        celltower_df = pd.read_sql(
            f"""
            SELECT ID, NAME, TOWER_TYPE, CAPACITY_GBPS, STATUS, REGION,
                   AVG_PACKET_LOSS, AVG_LATENCY_MS, AVG_ERROR_RATE,
                   AVG_HEALTH_SCORE
            FROM {table('CELLTOWER')}
            """,
            conn,
        )
        equipment_df = pd.read_sql(
            f"""
            SELECT ID, TOWER_ID_FK, TOWER, EQUIPMENT_TYPE, MANUFACTURER, EQP_MODEL,
                   FIRMWARE_VERSION, STATUS
            FROM {table('NETWORKEQUIPMENT')}
            """,
            conn,
        )
        health_df = pd.read_sql(
            f"""
            SELECT ID, EQUIPMENT_ID_FK, EQUIPMENT, MTBF_HOURS, FAILURE_RATE,
                   TEMPERATURE_AVG_C, POWER_CONSUMPTION_KW, HEALTH_SCORE
            FROM {table('EQUIPMENTHEALTH')}
            """,
            conn,
        )
        advisory_df = pd.read_sql(
            f"""
            SELECT MODEL, ADVISORY_TYPE, ISSUED_DATE, SEVERITY
            FROM {table('MODELADVISORY')}
            """,
            conn,
        )
    finally:
        conn.close()
    return celltower_df, equipment_df, health_df, advisory_df


def build_model(celltower_df, equipment_features_df, health_df, advisory_df, train_df, val_df, test_df):
    model = Model("Telco Failure Prediction From Deployed Tables")
    ontology = bind_predictive_base(
        model,
        dataframe_sources(
            model,
            {
                "CELLTOWER": celltower_df,
                "NETWORKEQUIPMENT": equipment_features_df,
                "EQUIPMENTHEALTH": health_df,
                "MODELADVISORY": advisory_df,
            },
        ),
    )
    CellTower = ontology.CellTower
    NetworkEquipment = ontology.NetworkEquipment
    EquipmentHealth = ontology.EquipmentHealth
    ModelAdvisory = ontology.ModelAdvisory

    gnn_graph = Graph(model, directed=False, weighted=False)
    model.define(gnn_graph.Edge.new(src=EquipmentHealth, dst=NetworkEquipment)).where(
        EquipmentHealth.equipment == NetworkEquipment,
    )
    model.define(gnn_graph.Edge.new(src=NetworkEquipment, dst=CellTower)).where(
        NetworkEquipment.tower == CellTower,
    )
    model.define(gnn_graph.Edge.new(src=ModelAdvisory, dst=NetworkEquipment)).where(
        ModelAdvisory.model == NetworkEquipment.eqp_model,
    )

    pt = PropertyTransformer(
        drop=[
            NetworkEquipment.tower_id_fk,
            NetworkEquipment.tower,
            NetworkEquipment.status,
            EquipmentHealth.equipment_id_fk,
            EquipmentHealth.equipment,
            CellTower.name,
            CellTower.avg_packet_loss,
            CellTower.avg_latency_ms,
            CellTower.avg_error_rate,
            CellTower.avg_health_score,
        ],
        category=[
            NetworkEquipment.equipment_type,
            NetworkEquipment.manufacturer,
            NetworkEquipment.eqp_model,
            NetworkEquipment.firmware_version,
            CellTower.tower_type,
            CellTower.status,
            CellTower.region,
            ModelAdvisory.advisory_type,
        ],
        continuous=[
            EquipmentHealth.failure_rate,
            EquipmentHealth.temperature_avg_c,
            EquipmentHealth.power_consumption_kw,
            EquipmentHealth.health_score,
            ModelAdvisory.severity,
        ],
        integer=[EquipmentHealth.mtbf_hours, CellTower.capacity_gbps],
    )

    TrainEqTable = model.Concept("TrainEqTable")
    ValEqTable = model.Concept("ValEqTable")
    TestEqTable = model.Concept("TestEqTable")
    model.define(TrainEqTable.new(model.data(train_df).to_schema()))
    model.define(ValEqTable.new(model.data(val_df).to_schema()))
    model.define(TestEqTable.new(model.data(test_df).to_schema()))

    Train = model.Relationship(f"{NetworkEquipment} has {Any:label}")
    model.define(Train(NetworkEquipment, TrainEqTable.at_risk)).where(
        NetworkEquipment.id == TrainEqTable.equipment_id,
    )
    Val = model.Relationship(f"{NetworkEquipment} has {Any:label}")
    model.define(Val(NetworkEquipment, ValEqTable.at_risk)).where(
        NetworkEquipment.id == ValEqTable.equipment_id,
    )
    Test = model.Relationship(f"{NetworkEquipment}")
    model.define(Test(NetworkEquipment)).where(
        NetworkEquipment.id == TestEqTable.equipment_id,
    )
    return model, NetworkEquipment, Train, Val, Test, gnn_graph, pt


def positive_probability(value):
    if isinstance(value, (list, tuple)):
        return float(value[1]) if len(value) > 1 else float(value[0])
    return float(value)


def main():
    equipment_df, train_df, val_df, test_df = equipment_splits()
    celltower_df, equipment_features_df, health_df, advisory_df = deployed_inputs()
    model, NetworkEquipment, Train, Val, Test, gnn_graph, pt = build_model(
        celltower_df,
        equipment_features_df,
        health_df,
        advisory_df,
        train_df,
        val_df,
        test_df,
    )

    gnn = GNN(
        exp_database=EXP_DATABASE,
        exp_schema=EXP_SCHEMA,
        graph=gnn_graph,
        property_transformer=pt,
        train=Train,
        validation=Val,
        task_type="binary_classification",
        eval_metric="roc_auc",
        has_time_column=False,
        stream_logs=False,
        seed=SEED,
        device="cpu",
        n_epochs=GNN_EPOCHS,
        lr=GNN_LR,
    )
    gnn.fit()
    NetworkEquipment.predictions = gnn.predictions(domain=Test)

    pred_df = (
        select(
            NetworkEquipment.id.alias("EQUIPMENT_ID"),
            NetworkEquipment.predictions.probs.alias("PROBS"),
            NetworkEquipment.predictions.predicted_labels.alias("PREDICTED_LABEL"),
        )
        .where(NetworkEquipment.predictions)
        .to_df()
    )
    pred_df["POS_PROB"] = pred_df["PROBS"].apply(positive_probability)
    pred_df["PREDICTED_LABEL"] = pred_df["PREDICTED_LABEL"].apply(int)
    pred_df = pred_df.merge(
        equipment_df[["ID"]].rename(columns={"ID": "EQUIPMENT_ID"}),
        on="EQUIPMENT_ID",
        how="inner",
    )

    conn = snowflake_connection()
    try:
        tower_lookup = pd.read_sql(
            f"SELECT ID AS EQUIPMENT_ID, TOWER AS TOWER_ID FROM {table('NETWORKEQUIPMENT')}",
            conn,
        )
    finally:
        conn.close()

    tower_scores = (
        pred_df.merge(tower_lookup, on="EQUIPMENT_ID", how="left")
        .groupby("TOWER_ID", dropna=False)["POS_PROB"]
        .sum()
        .reset_index()
        .rename(columns={"POS_PROB": "FAILURE_INTENSITY"})
        .sort_values("FAILURE_INTENSITY", ascending=False)
    )
    replace_table(tower_scores, "TOWER_FAILURE_SCORE")
    replace_table(pred_df[["EQUIPMENT_ID", "POS_PROB", "PREDICTED_LABEL"]], "EQUIPMENT_FAILURE_PREDICTION")


if __name__ == "__main__":
    main()
