"""Bundled CSVs, the GNN splits, and the rolling-horizon disruption data."""

from pathlib import Path

import pandas as pd

from .schema import (
    CapabilityOverride,
    Customer,
    Demand,
    Dependency,
    Input,
    InputMultiplier,
    InputUsage,
    Iteration,
    Period,
    Product,
    Supplier,
    SupplierObservation,
    SupplierProductCapacity,
    Test,
    TestTable,
    Train,
    TrainTable,
    Val,
    ValTable,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

HORIZON_END_PERIOD = 36

customers_df = pd.read_csv(DATA_DIR / "customers.csv")
model.define(Customer.new(model.data(customers_df).to_schema()))

products_df = pd.read_csv(DATA_DIR / "products.csv")
model.define(Product.new(model.data(products_df).to_schema()))

periods_df = pd.read_csv(DATA_DIR / "periods.csv")
model.define(Period.new(model.data(periods_df).to_schema()))

demand_df = pd.read_csv(DATA_DIR / "demand.csv")
model.define(Demand.new(model.data(demand_df).to_schema()))

suppliers_df = pd.read_csv(DATA_DIR / "suppliers.csv")
model.define(Supplier.new(model.data(suppliers_df).to_schema()))

spc_df = pd.read_csv(DATA_DIR / "supplier_product_capacity.csv")
model.define(SupplierProductCapacity.new(model.data(spc_df).to_schema()))

inputs_df = pd.read_csv(DATA_DIR / "inputs.csv")
model.define(Input.new(model.data(inputs_df).to_schema()))

input_usage_df = pd.read_csv(DATA_DIR / "input_usage.csv")
model.define(InputUsage.new(model.data(input_usage_df).to_schema()))

dependencies_df = pd.read_csv(DATA_DIR / "dependencies.csv")
model.define(Dependency.new(model.data(dependencies_df).to_schema()))

# Per-supplier static features for the GNN.
features_df = pd.read_csv(DATA_DIR / "supplier_features.csv")
f_data = model.data(features_df)
model.define(
    Supplier.lookup(id=f_data.supplier_id).equipment_age_months(f_data.equipment_age_months)
)
model.define(
    Supplier.lookup(id=f_data.supplier_id).geopolitical_exposure_score(
        f_data.geopolitical_exposure_score
    )
)
model.define(Supplier.lookup(id=f_data.supplier_id).region(f_data.region))
model.define(Supplier.lookup(id=f_data.supplier_id).process_node_nm(f_data.process_node_nm))
model.define(Supplier.lookup(id=f_data.supplier_id).workforce_size_k(f_data.workforce_size_k))

# Observations are numbered in row order: the historical rows first, then one
# future row per (supplier, month) of the horizon.
hist_df = pd.read_csv(DATA_DIR / "supplier_observations_historical.csv")
hist_df.insert(0, "id", range(1, len(hist_df) + 1))
model.define(SupplierObservation.new(model.data(hist_df).to_schema()))

future_obs_df = pd.DataFrame(
    [
        {"supplier_id": int(s), "period_id": p}
        for s in suppliers_df["id"]
        for p in range(1, HORIZON_END_PERIOD + 1)
    ]
)
future_obs_df.insert(0, "id", range(len(hist_df) + 1, len(hist_df) + len(future_obs_df) + 1))
model.define(SupplierObservation.new(model.data(future_obs_df).to_schema()))

# Temporal split: train on -23..-4, validate on -3..0, test on 1..36.
hist_rows = hist_df[["supplier_id", "period_id", "capability_pct"]]
train_split_df = hist_rows[hist_rows["period_id"] < -3].reset_index(drop=True)
val_split_df = hist_rows[hist_rows["period_id"] >= -3].reset_index(drop=True)
test_split_df = future_obs_df[["supplier_id", "period_id"]].reset_index(drop=True)

model.define(TrainTable.new(model.data(train_split_df).to_schema()))
model.define(ValTable.new(model.data(val_split_df).to_schema()))
model.define(TestTable.new(model.data(test_split_df).to_schema()))

model.define(Train(SupplierObservation, TrainTable.capability_pct)).where(
    SupplierObservation.supplier_id == TrainTable.supplier_id,
    SupplierObservation.period_id == TrainTable.period_id,
)
model.define(Val(SupplierObservation, ValTable.capability_pct)).where(
    SupplierObservation.supplier_id == ValTable.supplier_id,
    SupplierObservation.period_id == ValTable.period_id,
)
model.define(Test(SupplierObservation)).where(
    SupplierObservation.supplier_id == TestTable.supplier_id,
    SupplierObservation.period_id == TestTable.period_id,
)

# --------------------------------------------------
# Rolling horizon: three re-plans and the disruptions each one sees
# --------------------------------------------------
# Three solves: at the start of months 1, 5, 13 (one baseline + two disruption
# reveals). Each iteration applies the disruptions revealed by its start: a
# supplier disruption overrides that supplier's capability over its window, an
# input disruption lowers that input's availability.

disruption_reveal_df = pd.read_csv(DATA_DIR / "disruption_reveal.csv")

iter_specs = [
    {
        "iter_id": 0,
        "horizon_start": 1,
        "apply_disruptions_through_period": 0,
        "label": "Baseline (month 1, no disruption revealed)",
    },
    {
        "iter_id": 1,
        "horizon_start": 5,
        "apply_disruptions_through_period": 5,
        "label": "Re-plan at month 5 (Orion downtime revealed)",
    },
    {
        "iter_id": 2,
        "horizon_start": 13,
        "apply_disruptions_through_period": 13,
        "label": "Re-plan at month 13 (helium shortage revealed)",
    },
]
iterations_df = pd.DataFrame(iter_specs)[["iter_id", "horizon_start", "label"]]
model.define(Iteration.new(model.data(iterations_df).to_schema()))


def input_multipliers(input_avail):
    """Capacity multiplier per product given input availability per input id:
    product over inputs of (1 - intensity * (1 - avail))."""
    iu = input_usage_df.copy()
    iu["avail"] = iu["input_id"].map(input_avail).fillna(1.0)
    iu["mult"] = 1.0 - iu["intensity"] * (1.0 - iu["avail"])
    return iu.groupby("product_id")["mult"].prod()


override_rows, mult_rows = [], []
for spec in iter_specs:
    reveals = disruption_reveal_df[
        disruption_reveal_df["reveal_period"] <= spec["apply_disruptions_through_period"]
    ]
    input_avail = {int(i): 1.0 for i in inputs_df["id"]}
    for _, dis in reveals.iterrows():
        if dis["target_type"] == "supplier":
            for p in range(int(dis["start_period"]), int(dis["end_period"]) + 1):
                override_rows.append(
                    {
                        "iter_id": spec["iter_id"],
                        "supplier_id": int(dis["target_id"]),
                        "period_id": p,
                        "capability_pct": float(dis["parameter_value"]),
                    }
                )
        elif dis["target_type"] == "input":
            # Held low for the rest of the horizon.
            input_avail[int(dis["target_id"])] = float(dis["parameter_value"])
    mults = input_multipliers(input_avail)
    for product_id in products_df["id"]:
        mult_rows.append(
            {
                "iter_id": spec["iter_id"],
                "product_id": int(product_id),
                "mult": float(mults.get(product_id, 1.0)),
            }
        )

model.define(CapabilityOverride.new(model.data(pd.DataFrame(override_rows)).to_schema()))
model.define(InputMultiplier.new(model.data(pd.DataFrame(mult_rows)).to_schema()))
