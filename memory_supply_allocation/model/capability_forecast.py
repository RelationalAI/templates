"""Capability forecast: the supplier-capability GNN (or the bundled forecast snapshot), the clipped
forecast per supplier and month, and the forecast's row count."""

import pandas as pd
from relationalai.semantics import Float, Integer
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.std import aggregates
from relationalai.semantics.std import math as rmath

from .schema import (
    Supplier,
    SupplierCapabilityForecast,
    SupplierObservation,
    Test,
    Train,
    Val,
    model,
)
from .source import DATA_DIR

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Stage 2 (Predictive) configuration.
# Default behavior is an actual GNN regression run on Supplier capability;
# set USE_PRECOMPUTED_FORECAST=True to skip training and load the bundled
# forecast CSV directly (useful for fast iteration / offline reproducibility).
USE_PRECOMPUTED_FORECAST = False
GNN_N_EPOCHS = 30
GNN_LR = 0.005
GNN_SEED = 42

# --------------------------------------------------
# Stage 2: Predictive -- supplier capability forecast
# --------------------------------------------------
#
# Default: a node-regression GNN on Supplier predicts capability_pct per
# (supplier, period) from static features + historical observations; train.py
# trains and registers it, and every refresh predicts with the registered
# version. Either path populates the same SupplierCapabilityForecast concept;
# downstream stages don't care which ran.

if USE_PRECOMPUTED_FORECAST:
    gnn = None
    forecast_df = pd.read_csv(DATA_DIR / "supplier_capability_forecast.csv")
    model.define(SupplierCapabilityForecast.new(model.data(forecast_df).to_schema()))
else:
    # GNN graph: each observation links to its supplier; suppliers in the same
    # region link to each other so feature signal flows between similar fabs.
    gnn_graph = Graph(model, directed=True, weighted=False, name="gnn_graph")
    GEdge = gnn_graph.Edge
    model.define(GEdge.new(src=SupplierObservation, dst=Supplier)).where(
        SupplierObservation.supplier_id == Supplier.id
    )
    SupRef = Supplier.ref()
    model.define(GEdge.new(src=Supplier, dst=SupRef)).where(
        Supplier.region == SupRef.region,
        Supplier.id < SupRef.id,
    )

    pt = PropertyTransformer(
        drop=[
            Supplier.id,
            Supplier.name,
            Supplier.type,
            SupplierObservation.id,
            SupplierObservation.supplier_id,
            SupplierObservation.period_id,
            SupplierObservation.capability_pct,  # target — don't leak
        ],
        category=[Supplier.region],
        continuous=[Supplier.geopolitical_exposure_score],
        integer=[
            Supplier.equipment_age_months,
            Supplier.process_node_nm,
            Supplier.workforce_size_k,
        ],
    )

    # `name` ties this GNN to the registered model and version that
    # `reasoners.predictive.gnns.supplier_capability` names in raiconfig.yaml.
    gnn = GNN(
        name="supplier_capability",
        graph=gnn_graph,
        property_transformer=pt,
        train=Train,
        validation=Val,
        task_type="regression",
        eval_metric="rmse",
        has_time_column=False,
        stream_logs=False,
        seed=GNN_SEED,
        n_epochs=GNN_N_EPOCHS,
        lr=GNN_LR,
    )
    SupplierObservation.predictions = gnn.predictions(domain=Test)

    # Forecast = predicted capability, clipped to [0.85, 1.0].
    predicted = Float.ref()
    model.where(
        SupplierObservation.predictions.predicted_value(predicted),
    ).define(
        SupplierCapabilityForecast.new(
            supplier_id=SupplierObservation.supplier_id,
            period_id=SupplierObservation.period_id,
            capability_pct=rmath.round(rmath.clip(predicted, 0.85, 1.0), 4),
        )
    )

# The forecast's row count.
NumForecastRows = model.Relationship(f"the capability forecast has {Integer:num_rows} rows")
model.define(NumForecastRows(aggregates.count(SupplierCapabilityForecast)))
