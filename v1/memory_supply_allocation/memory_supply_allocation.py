"""Memory Supply Allocation (predictive + rules + prescriptive + paths) template.

Allocates constrained memory-chip supply across customers in a monthly rolling
horizon when supply is scarce and disruptions surface over time. Four reasoners
chained on one ontology:

- Stage 1 (Rules): derive `Customer.max_declared_yield_pct`,
  `Customer.elevated_floor_pct`, `Customer.depends_on` (graph edge), plus
  `Customer.is_dependency_spof`, from the dependency relation.
- Stage 2 (Predictive): load a pre-computed `SupplierCapabilityForecast` per
  (supplier, month). Regression target = `capability_pct`. A richer ontology
  could swap in a GNN node-classification model on suppliers (`rai-predictive-
  modeling`) -- pre-computed is used here for portability.
- Stage 3 (Prescriptive): monthly revenue-max LP over a 36-month horizon, run
  as a **3-step rolling horizon**. Baseline solve at month 1, then disruption
  reveals at months 5 and 13 trigger re-forecast and re-solve for the
  remaining horizon. Effective capacity per (product, period) = sum over
  suppliers of nominal x predicted capability, scaled by input availability.
- Stage 4 (Graph / PATHS): enumerate variable-length dependency chains via
  `model.path(Customer.depends_on.repeat(1, 3)).all_paths()` for root cause
  on the customer-customer graph. Two what-if branches: (1) supplier goes
  offline, (2) raw-material input shortage. Each surfaces affected (product,
  period) cells without re-solving the LP.

Run:
    python memory_supply_allocation.py

Output:
    Per-iteration LP status + total margin, plan-diff between rolling solves,
    per-customer service levels, dependency-chain enumeration, RCA tables,
    and the two what-if scenario analyses.
"""

from pathlib import Path

import pandas as pd
from relationalai.semantics import Any, Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

HBM3E_PRODUCT_ID = 1
HORIZON_END_PERIOD = 36
SOLVE_TIME_LIMIT_SEC = 60

# Stage 2 (Predictive) configuration.
# Default behavior is an actual GNN regression run on Supplier capability;
# set USE_PRECOMPUTED_FORECAST=True to skip training and load the bundled
# forecast CSV directly (useful for fast iteration / offline reproducibility).
USE_PRECOMPUTED_FORECAST = False
EXP_DATABASE = "MEMORY_SUPPLY"      # See README Prerequisites: create this DB + schema with the 4 RAI grants
EXP_SCHEMA = "EXPERIMENTS"
GNN_DEVICE = "cpu"                  # "cuda" if your predictive reasoner is GPU-sized
GNN_N_EPOCHS = 30
GNN_LR = 0.005
GNN_SEED = 42

pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 200)

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("memory_supply_allocation")
Concept, Property = model.Concept, model.Property

# Customer concept: chip buyers (hyperscalers, OEMs, equipment makers).
Customer = Concept("Customer", identify_by={"id": Integer})
Customer.name = Property(f"{Customer} has {String:name}")
Customer.industry = Property(f"{Customer} has {String:industry}")
Customer.base_service_floor_pct = Property(
    f"{Customer} has {Float:base_service_floor_pct}"
)
customers_df = pd.read_csv(DATA_DIR / "customers.csv")
model.define(Customer.new(model.data(customers_df).to_schema()))

# Product concept: memory SKUs.
Product = Concept("Product", identify_by={"id": Integer})
Product.name = Property(f"{Product} has {String:name}")
Product.family = Property(f"{Product} has {String:family}")
Product.unit_price_usd_per_gb = Property(f"{Product} has {Float:unit_price_usd_per_gb}")
Product.margin_pct = Property(f"{Product} has {Float:margin_pct}")
products_df = pd.read_csv(DATA_DIR / "products.csv")
model.define(Product.new(model.data(products_df).to_schema()))

# Period concept: monthly buckets across the 36-month horizon.
Period = Concept("Period", identify_by={"id": Integer})
Period.month_num = Property(f"{Period} has {Integer:month_num}")
Period.label = Property(f"{Period} has {String:label}")
periods_df = pd.read_csv(DATA_DIR / "periods.csv")
model.define(Period.new(model.data(periods_df).to_schema()))

# Demand junction concept: one row per (customer, product, period).
Demand = Concept(
    "Demand",
    identify_by={
        "customer_id": Integer,
        "product_id": Integer,
        "period_id": Integer,
    },
)
Demand.demand_usd = Property(f"{Demand} has {Float:demand_usd}")
demand_df = pd.read_csv(DATA_DIR / "demand.csv")
model.define(Demand.new(model.data(demand_df).to_schema()))

# Supplier concept: foundries / fabs producing memory SKUs.
Supplier = Concept("Supplier", identify_by={"id": Integer})
Supplier.name = Property(f"{Supplier} has {String:name}")
Supplier.type = Property(f"{Supplier} has {String:type}")
suppliers_df = pd.read_csv(DATA_DIR / "suppliers.csv")
model.define(Supplier.new(model.data(suppliers_df).to_schema()))

# SupplierProductCapacity: nominal monthly USD capacity per (supplier, product, period).
SupplierProductCapacity = Concept(
    "SupplierProductCapacity",
    identify_by={
        "supplier_id": Integer,
        "product_id": Integer,
        "period_id": Integer,
    },
)
SupplierProductCapacity.nominal_capacity_usd = Property(
    f"{SupplierProductCapacity} has {Float:nominal_capacity_usd}"
)
spc_df = pd.read_csv(DATA_DIR / "supplier_product_capacity.csv")
model.define(SupplierProductCapacity.new(model.data(spc_df).to_schema()))

# Input concept: raw materials / consumables (helium, neon, palladium).
Input = Concept("Input", identify_by={"id": Integer})
Input.name = Property(f"{Input} has {String:name}")
Input.description = Property(f"{Input} has {String:description}")
inputs_df = pd.read_csv(DATA_DIR / "inputs.csv")
model.define(Input.new(model.data(inputs_df).to_schema()))

# InputUsage: per (product, input) intensity (0 = no exposure, 1 = full exposure).
InputUsage = Concept(
    "InputUsage", identify_by={"product_id": Integer, "input_id": Integer}
)
InputUsage.intensity = Property(f"{InputUsage} has {Float:intensity}")
input_usage_df = pd.read_csv(DATA_DIR / "input_usage.csv")
model.define(InputUsage.new(model.data(input_usage_df).to_schema()))

# Dependency: downstream customer signals willingness to yield to upstream.
Dependency = Concept(
    "Dependency",
    identify_by={"downstream_id": Integer, "upstream_id": Integer},
)
Dependency.declared_yield_pct = Property(f"{Dependency} has {Float:declared_yield_pct}")
Dependency.elevated_floor_pct = Property(f"{Dependency} has {Float:elevated_floor_pct}")
dependencies_df = pd.read_csv(DATA_DIR / "dependencies.csv")
model.define(Dependency.new(model.data(dependencies_df).to_schema()))

# Disruption-reveal schedule for the rolling horizon (data, not ontology).
disruption_reveal_df = pd.read_csv(DATA_DIR / "disruption_reveal.csv")

# --------------------------------------------------
# Stage 1: Rules -- derive customer yield/floor properties + graph edges
# --------------------------------------------------

# Per-customer max declared yield across outgoing dependencies (0.0 if none).
Customer.max_declared_yield_pct = Property(
    f"{Customer} has {Float:max_declared_yield_pct}"
)
max_yield_expr = (
    aggregates.max(Dependency.declared_yield_pct)
    .per(Customer)
    .where(Dependency.downstream_id == Customer.id)
    | 0.0
)
model.define(Customer.max_declared_yield_pct(max_yield_expr))

# Per-customer elevated floor across incoming dependencies (0.0 if none).
Customer.elevated_floor_pct = Property(f"{Customer} has {Float:elevated_floor_pct}")
elevated_expr = (
    aggregates.max(Dependency.elevated_floor_pct)
    .per(Customer)
    .where(Dependency.upstream_id == Customer.id)
    | 0.0
)
model.define(Customer.elevated_floor_pct(elevated_expr))

# Customer-to-customer dependency relationship for Stage 4 path traversal.
Customer.depends_on = model.Relationship(
    f"{Customer:downstream} depends on {Customer:upstream}"
)
_c_down = Customer.ref("c_down")
_c_up = Customer.ref("c_up")
model.where(
    Dependency.downstream_id == _c_down.id,
    Dependency.upstream_id == _c_up.id,
).define(Customer.depends_on(_c_down, _c_up))

# Count of incoming dependencies (how many downstream signals protect this customer).
Customer.n_incoming_dependencies = Property(
    f"{Customer} has {Integer:n_incoming_dependencies}"
)
incoming_count_expr = (
    aggregates.count(Dependency)
    .per(Customer)
    .where(Dependency.upstream_id == Customer.id)
    | 0
)
model.define(Customer.n_incoming_dependencies(incoming_count_expr))

# Boolean: this customer's effective floor exceeds its base.
Customer.has_elevated_floor = model.Relationship(f"{Customer} has elevated floor")
model.where(
    Customer.elevated_floor_pct > Customer.base_service_floor_pct,
).define(Customer.has_elevated_floor())

# Boolean: single point of failure in the dependency graph (1 protecting edge).
Customer.is_dependency_spof = model.Relationship(
    f"{Customer} is dependency single point of failure"
)
model.where(
    Customer.n_incoming_dependencies == 1,
    Customer.elevated_floor_pct > Customer.base_service_floor_pct,
).define(Customer.is_dependency_spof())

# Decision variable property.
Demand.x_alloc = Property(f"{Demand} has {Float:x_alloc}")

# --------------------------------------------------
# Stage 2: Predictive -- supplier capability forecast
# --------------------------------------------------
#
# Default: train a node-regression GNN on Supplier predicting capability_pct
# per (supplier, period) from static features + historical observations.
# Set USE_PRECOMPUTED_FORECAST=True at the top of the file to skip training and
# load the bundled forecast CSV directly. Either path populates the same
# SupplierCapabilityForecast concept; downstream stages don't care which ran.

SupplierCapabilityForecast = Concept(
    "SupplierCapabilityForecast",
    identify_by={"supplier_id": Integer, "period_id": Integer},
)
SupplierCapabilityForecast.capability_pct = Property(
    f"{SupplierCapabilityForecast} has {Float:capability_pct}"
)

if USE_PRECOMPUTED_FORECAST:
    print("=" * 60)
    print("Stage 2: Loading pre-computed forecast (USE_PRECOMPUTED_FORECAST=True)")
    print("=" * 60)
    forecast_df_initial = pd.read_csv(DATA_DIR / "supplier_capability_forecast.csv")
    model.define(
        SupplierCapabilityForecast.new(model.data(forecast_df_initial).to_schema())
    )
else:
    print("=" * 60)
    print("Stage 2: Training supplier-capability GNN (regression, CPU)")
    print("=" * 60)

    # Per-supplier static features for the GNN.
    Supplier.equipment_age_months = Property(f"{Supplier} has {Integer:equipment_age_months}")
    Supplier.geopolitical_exposure_score = Property(
        f"{Supplier} has {Float:geopolitical_exposure_score}"
    )
    Supplier.region = Property(f"{Supplier} has {String:region}")
    Supplier.process_node_nm = Property(f"{Supplier} has {Integer:process_node_nm}")
    Supplier.workforce_size_k = Property(f"{Supplier} has {Integer:workforce_size_k}")
    features_df = pd.read_csv(DATA_DIR / "supplier_features.csv")
    f_data = model.data(features_df)
    model.define(
        Supplier.filter_by(id=f_data.supplier_id).equipment_age_months(
            f_data.equipment_age_months
        )
    )
    model.define(
        Supplier.filter_by(id=f_data.supplier_id).geopolitical_exposure_score(
            f_data.geopolitical_exposure_score
        )
    )
    model.define(Supplier.filter_by(id=f_data.supplier_id).region(f_data.region))
    model.define(
        Supplier.filter_by(id=f_data.supplier_id).process_node_nm(f_data.process_node_nm)
    )
    model.define(
        Supplier.filter_by(id=f_data.supplier_id).workforce_size_k(f_data.workforce_size_k)
    )

    # SupplierObservation: GNN source concept. One row per (supplier, period).
    # Historical rows (-23..0) carry capability_pct as the regression label;
    # future rows (1..36) are the prediction targets (no label).
    SupplierObservation = Concept(
        "SupplierObservation",
        identify_by={"supplier_id": Integer, "period_id": Integer},
    )
    SupplierObservation.capability_pct = Property(
        f"{SupplierObservation} has {Float:capability_pct}"
    )
    hist_df = pd.read_csv(DATA_DIR / "supplier_observations_historical.csv")
    model.define(SupplierObservation.new(model.data(hist_df).to_schema()))

    future_obs_df = pd.DataFrame(
        [
            {"supplier_id": int(s), "period_id": p}
            for s in suppliers_df["id"]
            for p in range(1, HORIZON_END_PERIOD + 1)
        ]
    )
    model.define(SupplierObservation.new(model.data(future_obs_df).to_schema()))

    # GNN graph: each observation links to its supplier; suppliers in the same
    # region link to each other so feature signal flows between similar fabs.
    gnn_graph = Graph(model, directed=True, weighted=False)
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
            Supplier.id, Supplier.name, Supplier.type,
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

    # Temporal split: train on -23..-4, validate on -3..0, test on 1..36.
    train_split_df = hist_df[hist_df["period_id"] < -3].reset_index(drop=True)
    val_split_df = hist_df[hist_df["period_id"] >= -3].reset_index(drop=True)
    test_split_df = future_obs_df[["supplier_id", "period_id"]].reset_index(drop=True)
    print(
        f"Split: train={len(train_split_df)} (periods -23..-4), "
        f"val={len(val_split_df)} (periods -3..0), "
        f"test={len(test_split_df)} (periods 1..{HORIZON_END_PERIOD})"
    )

    TrainTable = Concept("TrainTable")
    ValTable = Concept("ValTable")
    TestTable = Concept("TestTable")
    model.define(TrainTable.new(model.data(train_split_df).to_schema()))
    model.define(ValTable.new(model.data(val_split_df).to_schema()))
    model.define(TestTable.new(model.data(test_split_df).to_schema()))

    Train = model.Relationship(f"{SupplierObservation} has {Any:value}")
    model.define(Train(SupplierObservation, TrainTable.capability_pct)).where(
        SupplierObservation.supplier_id == TrainTable.supplier_id,
        SupplierObservation.period_id == TrainTable.period_id,
    )
    Val = model.Relationship(f"{SupplierObservation} has {Any:value}")
    model.define(Val(SupplierObservation, ValTable.capability_pct)).where(
        SupplierObservation.supplier_id == ValTable.supplier_id,
        SupplierObservation.period_id == ValTable.period_id,
    )
    Test = model.Relationship(f"{SupplierObservation}")
    model.define(Test(SupplierObservation)).where(
        SupplierObservation.supplier_id == TestTable.supplier_id,
        SupplierObservation.period_id == TestTable.period_id,
    )

    gnn = GNN(
        exp_database=EXP_DATABASE,
        exp_schema=EXP_SCHEMA,
        graph=gnn_graph,
        property_transformer=pt,
        train=Train,
        validation=Val,
        task_type="regression",
        eval_metric="rmse",
        has_time_column=False,
        stream_logs=False,
        seed=GNN_SEED,
        device=GNN_DEVICE,
        n_epochs=GNN_N_EPOCHS,
        lr=GNN_LR,
    )
    gnn.fit()
    SupplierObservation.predictions = gnn.predictions(domain=Test)

    pred_df = model.where(SupplierObservation.predictions).select(
        SupplierObservation.supplier_id.alias("supplier_id"),
        SupplierObservation.period_id.alias("period_id"),
        SupplierObservation.predictions.predicted_value.alias("capability_pct"),
    ).to_df()
    pred_df["supplier_id"] = pred_df["supplier_id"].astype(int)
    pred_df["period_id"] = pred_df["period_id"].astype(int)
    pred_df["capability_pct"] = pred_df["capability_pct"].clip(0.85, 1.0).round(4)
    print(f"GNN predictions: {len(pred_df)} rows for periods 1..{HORIZON_END_PERIOD}")

    forecast_df_initial = pred_df.copy()
    model.define(
        SupplierCapabilityForecast.new(model.data(forecast_df_initial).to_schema())
    )

print("\nPer-supplier capability_pct summary (post-Stage 2):")
fc_summary = forecast_df_initial.groupby("supplier_id")["capability_pct"].agg(
    ["mean", "min", "max"]
).round(3)
fc_summary["supplier"] = fc_summary.index.map(
    suppliers_df.set_index("id")["name"]
)
print(fc_summary.to_string())

# --------------------------------------------------
# Stage 3: Prescriptive -- monthly rolling-horizon LP
# --------------------------------------------------
#
# Three solves: at the start of months 1, 5, 13 (one baseline + two disruption
# reveals). Between solves, the disruption_reveal data is applied to a working
# forecast / input-availability state, and effective capacity is recomputed.
# Effective capacity per (product, period) is loaded into an EffectiveCapacity
# concept with an iter_id discriminator so the LP at iteration K references
# only its own rows.

EffectiveCapacity = Concept(
    "EffectiveCapacity",
    identify_by={
        "iter_id": Integer,
        "product_id": Integer,
        "period_id": Integer,
    },
)
EffectiveCapacity.effective_capacity_usd = Property(
    f"{EffectiveCapacity} has {Float:effective_capacity_usd}"
)


def compute_effective_capacity(forecast_df_state, input_avail_state):
    """Compute effective capacity per (product, period) given current forecast
    and input availability state. Returns a DataFrame with columns
    product_id, period_id, effective_capacity_usd."""
    sp = spc_df.merge(forecast_df_state, on=["supplier_id", "period_id"])
    sp["eff_supply_usd"] = sp["nominal_capacity_usd"] * sp["capability_pct"]
    per_prod_period = (
        sp.groupby(["product_id", "period_id"])["eff_supply_usd"].sum().reset_index()
    )

    # Multiply by input-availability factor per product:
    #   product_multiplier = product over inputs of (1 - intensity * (1 - avail))
    iu = input_usage_df.copy()
    iu["avail"] = iu["input_id"].map(input_avail_state).fillna(1.0)
    iu["mult"] = 1.0 - iu["intensity"] * (1.0 - iu["avail"])
    per_prod_mult = iu.groupby("product_id")["mult"].prod()

    per_prod_period["mult"] = per_prod_period["product_id"].map(per_prod_mult).fillna(1.0)
    per_prod_period["effective_capacity_usd"] = (
        per_prod_period["eff_supply_usd"] * per_prod_period["mult"]
    )
    return per_prod_period[["product_id", "period_id", "effective_capacity_usd"]]


# Rolling-horizon state.
working_forecast_df = forecast_df_initial.copy()
working_input_avail = {int(r["id"]): 1.0 for _, r in inputs_df.iterrows()}

# Each rolling iteration runs from horizon_start to month 36.
iter_specs = [
    {"iter_id": 0, "horizon_start": 1,  "apply_disruptions_through_period": 0,
     "label": "Baseline (month 1, no disruption revealed)"},
    {"iter_id": 1, "horizon_start": 5,  "apply_disruptions_through_period": 5,
     "label": "Re-plan at month 5 (Orion downtime revealed)"},
    {"iter_id": 2, "horizon_start": 13, "apply_disruptions_through_period": 13,
     "label": "Re-plan at month 13 (helium shortage revealed)"},
]

scenario_results = []
prior_alloc_df = None  # for plan-diff between iterations

for spec in iter_specs:
    iter_id = spec["iter_id"]
    horizon_start = spec["horizon_start"]
    print(f"\n{'=' * 60}\nStage 3 iteration {iter_id}: {spec['label']}\n{'=' * 60}")

    # Apply any disruptions revealed at or before this iteration's start.
    reveals_to_apply = disruption_reveal_df[
        disruption_reveal_df["reveal_period"] <= spec["apply_disruptions_through_period"]
    ]
    for _, dis in reveals_to_apply.iterrows():
        if dis["target_type"] == "supplier":
            mask = (
                (working_forecast_df["supplier_id"] == dis["target_id"])
                & (working_forecast_df["period_id"] >= dis["start_period"])
                & (working_forecast_df["period_id"] <= dis["end_period"])
            )
            working_forecast_df.loc[mask, "capability_pct"] = dis["parameter_value"]
        elif dis["target_type"] == "input":
            # Apply for the disrupted window only -- before/after stays at 1.0.
            # For simplicity in the template, hold-low through end_period.
            working_input_avail[int(dis["target_id"])] = dis["parameter_value"]

    # Compute effective capacity for this iteration and load as ontology rows
    # tagged with this iter_id. Load only the rows for the current horizon
    # window (period_id >= horizon_start) -- earlier periods are already locked
    # by prior solves.
    eff_cap_df = compute_effective_capacity(working_forecast_df, working_input_avail)
    eff_cap_df = eff_cap_df[eff_cap_df["period_id"] >= horizon_start].copy()
    eff_cap_df["iter_id"] = iter_id
    eff_cap_df["effective_capacity_usd"] = eff_cap_df["effective_capacity_usd"].astype(float)
    model.define(EffectiveCapacity.new(model.data(eff_cap_df).to_schema()))

    print(f"  Horizon: months {horizon_start}-{HORIZON_END_PERIOD}, "
          f"effective-capacity cells loaded: {len(eff_cap_df)}")

    # Fresh Problem.
    problem = Problem(model, Float)
    alloc = problem.solve_for(
        Demand.x_alloc,
        type="cont",
        lower=0.0,
        name=["alloc", Demand.customer_id, Demand.product_id, Demand.period_id],
        where=[Demand.period_id >= horizon_start],
        populate=False,
    )

    # Capacity constraint scoped to this iteration's effective-capacity rows.
    problem.satisfy(
        model.where(EffectiveCapacity.iter_id == iter_id).require(
            sum(Demand.x_alloc).per(EffectiveCapacity).where(
                Demand.product_id == EffectiveCapacity.product_id,
                Demand.period_id == EffectiveCapacity.period_id,
            )
            <= EffectiveCapacity.effective_capacity_usd
        ),
        name=["cap", EffectiveCapacity.iter_id, EffectiveCapacity.product_id, EffectiveCapacity.period_id],
    )

    # Demand cap (yield-aware), base floor, elevated floor -- all scoped to horizon.
    problem.satisfy(
        model.where(
            Demand.customer_id == Customer.id,
            Demand.period_id >= horizon_start,
        ).require(
            Demand.x_alloc
            <= (1.0 - Customer.max_declared_yield_pct) * Demand.demand_usd
        ),
        name=["dcap", Demand.customer_id, Demand.product_id, Demand.period_id],
    )
    problem.satisfy(
        model.where(
            Demand.customer_id == Customer.id,
            Demand.period_id >= horizon_start,
        ).require(
            Demand.x_alloc >= Customer.base_service_floor_pct * Demand.demand_usd
        ),
        name=["bfloor", Demand.customer_id, Demand.product_id, Demand.period_id],
    )
    problem.satisfy(
        model.where(
            Demand.customer_id == Customer.id,
            Demand.period_id >= horizon_start,
        ).require(
            Demand.x_alloc >= Customer.elevated_floor_pct * Demand.demand_usd
        ),
        name=["efloor", Demand.customer_id, Demand.product_id, Demand.period_id],
    )

    # Objective: margin-weighted allocation over the current horizon.
    problem.maximize(
        sum(Demand.x_alloc * Product.margin_pct).where(
            Demand.product_id == Product.id,
            Demand.period_id >= horizon_start,
        )
    )

    problem.solve("highs", time_limit_sec=SOLVE_TIME_LIMIT_SEC)
    si = problem.solve_info()
    si.display()

    scenario_results.append(
        {
            "iter_id": iter_id,
            "label": spec["label"],
            "horizon_start": horizon_start,
            "status": str(si.termination_status),
            "objective": si.objective_value,
        }
    )
    if si.termination_status != "OPTIMAL":
        print(f"  Status: {si.termination_status} -- skipping detail output.")
        prior_alloc_df = None
        continue

    print(f"  Status: {si.termination_status}")
    print(f"  Total margin over horizon (months {horizon_start}-{HORIZON_END_PERIOD}): "
          f"${si.objective_value:,.2f}")

    # Extract solution values.
    value_ref = Float.ref()
    sol = model.select(
        alloc.demand.customer_id.alias("customer_id"),
        alloc.demand.product_id.alias("product_id"),
        alloc.demand.period_id.alias("period_id"),
        value_ref.alias("alloc_usd"),
    ).where(alloc.values(0, value_ref)).to_df()

    # Plan-diff vs prior iteration's allocation (only overlapping periods).
    if prior_alloc_df is not None:
        overlap = sol.merge(
            prior_alloc_df,
            on=["customer_id", "product_id", "period_id"],
            suffixes=("_now", "_prior"),
        )
        overlap["delta_usd"] = overlap["alloc_usd_now"] - overlap["alloc_usd_prior"]
        per_customer_delta = (
            overlap.groupby("customer_id")["delta_usd"].sum().rename("delta_usd_total")
        )
        per_customer_delta = per_customer_delta.reset_index().merge(
            customers_df[["id", "name"]], left_on="customer_id", right_on="id"
        )
        per_customer_delta["delta_$M"] = per_customer_delta["delta_usd_total"] / 1e6
        per_customer_delta = per_customer_delta[["name", "delta_$M"]].sort_values(
            "delta_$M"
        )
        print(f"\n  === Plan diff vs prior iteration (months {horizon_start}-{HORIZON_END_PERIOD}) ===")
        print(per_customer_delta.to_string(index=False))

    prior_alloc_df = sol.copy()

    # Per-customer service level over the current horizon.
    sol_merged = sol.merge(
        demand_df[["customer_id", "product_id", "period_id", "demand_usd"]],
        on=["customer_id", "product_id", "period_id"],
    )
    per_customer = (
        sol_merged.groupby("customer_id")[["alloc_usd", "demand_usd"]].sum()
        .assign(service_level=lambda d: d["alloc_usd"] / d["demand_usd"])
        .join(customers_df.set_index("id")[["name", "industry"]])
        .sort_values("demand_usd", ascending=False)
    )
    per_customer["alloc_$B"] = per_customer["alloc_usd"] / 1e9
    per_customer["demand_$B"] = per_customer["demand_usd"] / 1e9
    per_customer["service_%"] = (per_customer["service_level"] * 100).round(1)
    print("\n  === Per-customer service level (over current horizon) ===")
    print(per_customer[["name", "industry", "demand_$B", "alloc_$B", "service_%"]]
          .to_string(index=False))

# --------------------------------------------------
# Stage 3 summary -- persist outcomes to ontology
# --------------------------------------------------

# Persist rolling-horizon outcomes for downstream querying.
ScenarioOutcome = Concept(
    "ScenarioOutcome",
    identify_by={"iter_id": Integer},
)
ScenarioOutcome.label = Property(f"{ScenarioOutcome} has {String:label}")
ScenarioOutcome.horizon_start = Property(f"{ScenarioOutcome} has {Integer:horizon_start}")
ScenarioOutcome.status = Property(f"{ScenarioOutcome} has {String:status}")
ScenarioOutcome.total_margin_usd = Property(
    f"{ScenarioOutcome} has {Float:total_margin_usd}"
)
outcomes_df = pd.DataFrame(
    [
        {
            "iter_id": r["iter_id"],
            "label": r["label"],
            "horizon_start": r["horizon_start"],
            "status": r["status"],
            "total_margin_usd": r["objective"] if r["objective"] is not None else 0.0,
        }
        for r in scenario_results
    ]
)
model.define(ScenarioOutcome.new(model.data(outcomes_df).to_schema()))

print("\n" + "=" * 60)
print("Rolling-horizon summary")
print("=" * 60)
for r in scenario_results:
    obj_str = f"${r['objective']:,.2f}" if r["objective"] is not None else "N/A"
    print(f"  iter={r['iter_id']} months={r['horizon_start']}-{HORIZON_END_PERIOD}: "
          f"{r['status']:12s} margin={obj_str}")

# --------------------------------------------------
# Stage 4: Graph (PATHS) -- dependency chains, RCA, and what-if
# --------------------------------------------------

print("\n" + "=" * 60)
print("Stage 4: Dependency-chain analysis (PATHS), RCA, and what-if")
print("=" * 60)

p_pattern = model.path(Customer.depends_on.repeat(1, 3))
paths_df = model.where(
    p := p_pattern.all_paths(),
).select(
    p.alias("path_id"),
    p.length.alias("hops"),
    p.nodes["index"].alias("step"),
    Customer(p.nodes).name.alias("customer"),
).to_df()
paths_df["hops"] = paths_df["hops"].astype(int)
paths_df["step"] = paths_df["step"].astype(int)

chains = (
    paths_df.sort_values(["path_id", "step"])
    .groupby("path_id")
    .agg(
        hops=("hops", "first"),
        chain=("customer", lambda s: " -> ".join(s)),
    )
    .reset_index()
    .sort_values(["hops", "chain"])
)
print(f"\n  Total customer-customer dependency paths (1-3 hops): {len(chains)}")
print("\n  === Dependency chains ===")
print(chains[["hops", "chain"]].to_string(index=False))

# Read ontology-resident SPOF flag (defined in Stage 1).
spof_df = model.where(Customer.is_dependency_spof()).select(
    Customer.name.alias("spof_customer"),
).to_df()
print("\n  === Customers flagged as dependency SPOFs (ontology query) ===")
print(spof_df.to_string(index=False) if not spof_df.empty else "  (none)")

# ---- What-if 1: Supplier goes offline ----
# For each supplier, recompute effective capacity with capability=0 for all
# periods, and surface affected (product, period) cells where the cap drop
# exceeds 10% vs baseline. No re-solve -- pure structural impact.

print("\n" + "=" * 60)
print("What-if 1: supplier-offline impact (no re-solve)")
print("=" * 60)
baseline_eff = compute_effective_capacity(
    forecast_df_initial, {int(r["id"]): 1.0 for _, r in inputs_df.iterrows()}
)
baseline_eff = baseline_eff.rename(columns={"effective_capacity_usd": "baseline_cap"})

what_if_supplier_rows = []
for _, sup in suppliers_df.iterrows():
    perturbed_forecast = forecast_df_initial.copy()
    perturbed_forecast.loc[
        perturbed_forecast["supplier_id"] == sup["id"], "capability_pct"
    ] = 0.0
    perturbed_eff = compute_effective_capacity(
        perturbed_forecast, {int(r["id"]): 1.0 for _, r in inputs_df.iterrows()}
    )
    perturbed_eff = perturbed_eff.rename(
        columns={"effective_capacity_usd": "offline_cap"}
    )
    joined = baseline_eff.merge(perturbed_eff, on=["product_id", "period_id"])
    joined["cap_drop_pct"] = 1.0 - (joined["offline_cap"] / joined["baseline_cap"])
    significant = joined[joined["cap_drop_pct"] > 0.10]
    affected_products = significant["product_id"].unique()
    what_if_supplier_rows.append(
        {
            "supplier_id": int(sup["id"]),
            "supplier": sup["name"],
            "n_affected_cells": int(len(significant)),
            "max_cap_drop_pct": float(significant["cap_drop_pct"].max())
            if not significant.empty else 0.0,
            "affected_products": ", ".join(
                products_df.set_index("id").loc[affected_products, "name"].tolist()
            ),
        }
    )
what_if_supplier_df = pd.DataFrame(what_if_supplier_rows)

# Persist what-if 1 output back to the ontology so a downstream analyst can
# query supplier-offline risk without re-running the script.
Supplier.offline_impact_cells = Property(f"{Supplier} has {Integer:offline_impact_cells}")
Supplier.offline_max_cap_drop_pct = Property(
    f"{Supplier} has {Float:offline_max_cap_drop_pct}"
)
impact_bind = model.data(
    what_if_supplier_df[["supplier_id", "n_affected_cells", "max_cap_drop_pct"]]
)
model.define(
    Supplier.filter_by(id=impact_bind.supplier_id).offline_impact_cells(
        impact_bind.n_affected_cells
    )
)
model.define(
    Supplier.filter_by(id=impact_bind.supplier_id).offline_max_cap_drop_pct(
        impact_bind.max_cap_drop_pct
    )
)

print("\n  === Supplier-offline impact (each supplier in isolation) ===")
display_supplier = what_if_supplier_df.drop(columns=["supplier_id"]).copy()
display_supplier["max_cap_drop_%"] = (display_supplier["max_cap_drop_pct"] * 100).round(1)
display_supplier = display_supplier[
    ["supplier", "n_affected_cells", "max_cap_drop_%", "affected_products"]
]
print(display_supplier.to_string(index=False))

# ---- What-if 2: Raw-material input shortage ----
# Each input drops to 30% availability. Recompute effective capacity, surface
# which products are most affected by their exposure (input intensity).

print("\n" + "=" * 60)
print("What-if 2: input-shortage impact (no re-solve)")
print("=" * 60)
what_if_input_rows = []
for _, inp in inputs_df.iterrows():
    avail = {int(r["id"]): 1.0 for _, r in inputs_df.iterrows()}
    avail[int(inp["id"])] = 0.30
    perturbed_eff = compute_effective_capacity(forecast_df_initial, avail)
    perturbed_eff = perturbed_eff.rename(
        columns={"effective_capacity_usd": "shortage_cap"}
    )
    joined = baseline_eff.merge(perturbed_eff, on=["product_id", "period_id"])
    joined["cap_drop_pct"] = 1.0 - (joined["shortage_cap"] / joined["baseline_cap"])
    significant = joined[joined["cap_drop_pct"] > 0.05]
    by_product = (
        significant.groupby("product_id")["cap_drop_pct"].mean().round(3)
        .rename("avg_cap_drop")
    )
    by_product_named = by_product.reset_index().merge(
        products_df[["id", "name"]], left_on="product_id", right_on="id"
    )
    what_if_input_rows.append(
        {
            "input_id": int(inp["id"]),
            "input": inp["name"],
            "n_affected_cells": int(len(significant)),
            "affected_products_avg_drop": ", ".join(
                f"{row['name']}={row['avg_cap_drop']:.0%}"
                for _, row in by_product_named.iterrows()
            ),
        }
    )
what_if_input_df = pd.DataFrame(what_if_input_rows)

# Persist what-if 2 output back to the ontology so the input-shortage risk
# ranking is queryable after the script exits.
Input.shortage_impact_cells = Property(f"{Input} has {Integer:shortage_impact_cells}")
input_bind = model.data(what_if_input_df[["input_id", "n_affected_cells"]])
model.define(
    Input.filter_by(id=input_bind.input_id).shortage_impact_cells(
        input_bind.n_affected_cells
    )
)

print("\n  === Input-shortage impact (each input at 30% availability) ===")
print(what_if_input_df.drop(columns=["input_id"]).to_string(index=False))

# ---- Headline ----
print("\n" + "=" * 60)
print("Headline")
print("=" * 60)
spof_names = spof_df["spof_customer"].tolist()
if spof_names:
    print(f"  Customer-graph SPOF(s): {', '.join(spof_names)}")
multihop = chains[chains["hops"] > 1]
if not multihop.empty:
    print("  Multi-hop dependency chains:")
    for chain in multihop["chain"]:
        print(f"    {chain}")
worst_supplier = max(what_if_supplier_rows, key=lambda r: r["n_affected_cells"])
print(f"  Supplier with widest offline impact: {worst_supplier['supplier']} "
      f"({worst_supplier['n_affected_cells']} affected cells, "
      f"max cap drop {worst_supplier['max_cap_drop_pct'] * 100:.1f}%)")
worst_input = max(what_if_input_rows, key=lambda r: r["n_affected_cells"])
print(f"  Input with widest shortage impact: {worst_input['input']} "
      f"({worst_input['n_affected_cells']} affected cells)")
margins = [r["objective"] for r in scenario_results if r["objective"] is not None]
if len(margins) >= 2:
    erosion = margins[0] - margins[-1]
    print(f"  Margin erosion across rolling horizon (iter 0 -> iter "
          f"{len(margins) - 1}): ${erosion:,.2f}")
