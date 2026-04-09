"""Energy grid planning (multi-reasoner) template.

This script demonstrates a four-stage multi-reasoner pipeline in RelationalAI,
combining predictive enrichment, graph analysis, rules-based compliance, and
prescriptive optimization on a single shared ontology:

- Stage 1 -- Predict: load a pre-trained GNN for substation demand forecasting
  (or fall back to the demand_forecasts CSV). Enriches each Substation with a
  predicted_load property consumed by downstream stages.
- Stage 2 -- Graph: build the transmission grid topology in a separate graph
  model, compute weakly connected components, Louvain community detection,
  betweenness/degree/eigenvector centrality, and identify structurally critical
  substations. Results are written back to the main ontology.
- Stage 3 -- Rules: declarative interconnection queue compliance checks
  (capacity, structural criticality, low-carbon mandate) that consume Stage 1
  and 2 enrichments.
- Stage 4 -- Prescriptive: joint DC approval + grid upgrade optimization using
  InvestmentLevel as a Scenario Concept. One solve across 5 budget levels
  produces a Pareto frontier with results queryable directly from the ontology.

Run:
    /opt/homebrew/bin/python3.11 energy_grid_planning.py

Output:
    Prints a four-stage pipeline summary:
    - Stage 1: substation load forecasts with growth rates and breach detection
    - Stage 2: grid connectivity (WCC), community structure (Louvain), centrality
      ranking, and structurally critical substations
    - Stage 3: compliance table (10 DC requests vs 3 rules: capacity, low-carbon,
      structural risk)
    - Stage 4: Pareto frontier across 5 investment levels ($200M-$600M) with
      per-level DC approvals, upgrade selections, marginal analysis, and knee point
"""

from pathlib import Path

import pandas as pd
from pandas import read_csv
from relationalai.semantics import Boolean, Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

LOW_CARBON_TARGET = 0.30  # 30% of generation must be low-carbon (renewable + nuclear)
EMISSIONS_CAP = 50000  # tons
AMORTIZATION_YEARS = 20  # upgrade cost spread over 20 years
CRITICAL_THRESHOLD = 3  # top-N substations by combined centrality rank are "structurally critical"


# --------------------------------------------------
# CSV loader with boolean auto-detection
# --------------------------------------------------

def load_csv(filename):
    df = read_csv(DATA_DIR / filename)
    for col in df.columns:
        if df[col].dtype == object and set(df[col].dropna().unique()).issubset({"true", "false"}):
            df[col] = df[col].map({"true": True, "false": False})
    return df


# --------------------------------------------------
# Load all CSV data
# --------------------------------------------------

substations_df = load_csv("substations.csv")
generators_df = load_csv("generators.csv")
transmission_lines_df = load_csv("transmission_lines.csv")
load_zones_df = load_csv("load_zones.csv")
demand_periods_df = load_csv("demand_periods.csv")
renewable_profiles_df = load_csv("renewable_profiles.csv")
maintenance_windows_df = load_csv("maintenance_windows.csv")
customers_df = load_csv("customers.csv")
data_center_requests_df = load_csv("data_center_requests.csv")
substation_upgrades_df = load_csv("substation_upgrades.csv")
demand_forecasts_df = load_csv("demand_forecasts.csv")
load_history_df = load_csv("load_history.csv")
dc_announcements_df = load_csv("dc_announcements.csv")

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

model = Model("Energy Grid Infrastructure")

# Substation
Substation = model.Concept("Substation", identify_by={"id": String})
Substation.name = model.Property(f"{Substation} has {String:name}")
Substation.voltage_kv = model.Property(f"{Substation} has voltage {Float:voltage_kv} kV")
Substation.max_capacity_mw = model.Property(f"{Substation} has max capacity {Float:max_capacity_mw} MW")
Substation.current_load_mw = model.Property(f"{Substation} has current load {Float:current_load_mw} MW")
Substation.latitude = model.Property(f"{Substation} at latitude {Float:latitude}")
Substation.longitude = model.Property(f"{Substation} at longitude {Float:longitude}")

# Generator
Generator = model.Concept("Generator", identify_by={"id": String})
Generator.name = model.Property(f"{Generator} has {String:name}")
Generator.gen_type = model.Property(f"{Generator} has type {String:gen_type}")
Generator.capacity_mw = model.Property(f"{Generator} has capacity {Float:capacity_mw} MW")
Generator.min_output_mw = model.Property(f"{Generator} has minimum output {Float:min_output_mw} MW")
Generator.ramp_rate_mw_per_hr = model.Property(f"{Generator} has ramp rate {Float:ramp_rate_mw_per_hr} MW/hr")
Generator.startup_cost = model.Property(f"{Generator} has startup cost {Float:startup_cost}")
Generator.marginal_cost = model.Property(f"{Generator} has marginal cost {Float:marginal_cost} per MWh")
Generator.min_up_time_hrs = model.Property(f"{Generator} has minimum up time {Integer:min_up_time_hrs} hours")
Generator.min_down_time_hrs = model.Property(f"{Generator} has minimum down time {Integer:min_down_time_hrs} hours")
Generator.emissions_rate = model.Property(f"{Generator} has emissions rate {Float:emissions_rate} tons/MWh")
Generator.is_renewable = model.Property(f"{Generator} is renewable {Boolean:is_renewable}")
Generator.substation = model.Relationship(f"{Generator} connected to {Substation}")

# TransmissionLine
TransmissionLine = model.Concept("TransmissionLine", identify_by={"id": String})
TransmissionLine.from_substation = model.Relationship(
    f"{TransmissionLine} originates at {Substation}", short_name="from_substation")
TransmissionLine.to_substation = model.Relationship(
    f"{TransmissionLine} terminates at {Substation}", short_name="to_substation")
TransmissionLine.capacity_mw = model.Property(f"{TransmissionLine} has capacity {Float:capacity_mw} MW")
TransmissionLine.length_km = model.Property(f"{TransmissionLine} has length {Float:length_km} km")
TransmissionLine.impedance = model.Property(f"{TransmissionLine} has impedance {Float:impedance}")
TransmissionLine.is_active = model.Property(f"{TransmissionLine} is active {Boolean:is_active}")
TransmissionLine.maintenance_priority = model.Property(
    f"{TransmissionLine} has maintenance priority {String:maintenance_priority}")

# LoadZone
LoadZone = model.Concept("LoadZone", identify_by={"id": String})
LoadZone.name = model.Property(f"{LoadZone} has {String:name}")
LoadZone.peak_demand_mw = model.Property(f"{LoadZone} has peak demand {Float:peak_demand_mw} MW")
LoadZone.base_demand_mw = model.Property(f"{LoadZone} has base demand {Float:base_demand_mw} MW")

# DemandPeriod
DemandPeriod = model.Concept("DemandPeriod", identify_by={"id": String})
DemandPeriod.load_zone = model.Relationship(f"{DemandPeriod} in {LoadZone}")
DemandPeriod.period = model.Property(f"{DemandPeriod} at hour {Integer:period}")
DemandPeriod.demand_mw = model.Property(f"{DemandPeriod} has demand {Float:demand_mw} MW")
DemandPeriod.price_per_mwh = model.Property(f"{DemandPeriod} has price {Float:price_per_mwh} per MWh")

# RenewableProfile
RenewableProfile = model.Concept("RenewableProfile", identify_by={"id": String})
RenewableProfile.generator = model.Relationship(f"{RenewableProfile} for {Generator}")
RenewableProfile.period = model.Property(f"{RenewableProfile} at hour {Integer:period}")
RenewableProfile.capacity_factor = model.Property(
    f"{RenewableProfile} has capacity factor {Float:capacity_factor}")

# MaintenanceWindow
MaintenanceWindow = model.Concept("MaintenanceWindow", identify_by={"id": String})
MaintenanceWindow.asset_type = model.Property(f"{MaintenanceWindow} on asset type {String:asset_type}")
MaintenanceWindow.asset_id = model.Property(f"{MaintenanceWindow} on asset {String:asset_id}")
MaintenanceWindow.start_period = model.Property(
    f"{MaintenanceWindow} starts at hour {Integer:start_period}")
MaintenanceWindow.end_period = model.Property(f"{MaintenanceWindow} ends at hour {Integer:end_period}")
MaintenanceWindow.is_planned = model.Property(f"{MaintenanceWindow} is planned {Boolean:is_planned}")

# Customer
Customer = model.Concept("Customer", identify_by={"id": String})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.load_zone = model.Relationship(f"{Customer} in {LoadZone}")
Customer.contracted_demand_mw = model.Property(
    f"{Customer} has contracted demand {Float:contracted_demand_mw} MW")
Customer.flexibility_pct = model.Property(f"{Customer} has flexibility {Float:flexibility_pct} percent")
Customer.curtailment_cost_per_mwh = model.Property(
    f"{Customer} has curtailment cost {Float:curtailment_cost_per_mwh} per MWh")

# DataCenterRequest
DataCenterRequest = model.Concept("DataCenterRequest", identify_by={"id": String})
DataCenterRequest.name = model.Property(f"{DataCenterRequest} has {String:name}")
DataCenterRequest.hyperscaler = model.Property(
    f"{DataCenterRequest} from hyperscaler {String:hyperscaler}")
DataCenterRequest.requested_mw = model.Property(
    f"{DataCenterRequest} requesting {Float:requested_mw} MW")
DataCenterRequest.substation = model.Relationship(f"{DataCenterRequest} connected to {Substation}")
DataCenterRequest.annual_revenue_per_mw = model.Property(
    f"{DataCenterRequest} has annual revenue {Float:annual_revenue_per_mw} per MW")
DataCenterRequest.pue = model.Property(
    f"{DataCenterRequest} has power usage effectiveness {Float:pue}")
DataCenterRequest.is_ai_workload = model.Property(
    f"{DataCenterRequest} is AI workload {Boolean:is_ai_workload}")
DataCenterRequest.cooling_type = model.Property(
    f"{DataCenterRequest} has cooling type {String:cooling_type}")
DataCenterRequest.low_carbon_requirement_pct = model.Property(
    f"{DataCenterRequest} has low-carbon requirement {Float:low_carbon_requirement_pct} percent")
DataCenterRequest.queue_position = model.Property(
    f"{DataCenterRequest} has queue position {Integer:queue_position}")
DataCenterRequest.status = model.Property(f"{DataCenterRequest} has status {String:status}")

# SubstationUpgrade
SubstationUpgrade = model.Concept("SubstationUpgrade", identify_by={"id": String})
SubstationUpgrade.substation = model.Relationship(f"{SubstationUpgrade} at {Substation}")
SubstationUpgrade.capacity_increase_mw = model.Property(
    f"{SubstationUpgrade} adds {Float:capacity_increase_mw} MW")
SubstationUpgrade.cost_million = model.Property(
    f"{SubstationUpgrade} costs {Float:cost_million} million dollars")
SubstationUpgrade.lead_time_months = model.Property(
    f"{SubstationUpgrade} has lead time {Integer:lead_time_months} months")
SubstationUpgrade.enables_low_carbon = model.Property(
    f"{SubstationUpgrade} enables low-carbon connection {Boolean:enables_low_carbon}")

# DemandForecast
DemandForecast = model.Concept("DemandForecast", identify_by={"id": String})
DemandForecast.substation = model.Relationship(f"{DemandForecast} for {Substation}")
DemandForecast.forecast_period = model.Property(
    f"{DemandForecast} looking ahead {Integer:forecast_period} months")
DemandForecast.predicted_load_mw = model.Property(
    f"{DemandForecast} predicts {Float:predicted_load_mw} MW load")
DemandForecast.confidence = model.Property(f"{DemandForecast} has confidence {Float:confidence}")
DemandForecast.includes_dc_growth = model.Property(
    f"{DemandForecast} includes DC growth {Boolean:includes_dc_growth}")

# LoadHistory
LoadHistory = model.Concept("LoadHistory", identify_by={"id": String})
LoadHistory.reading_date = model.Property(f"{LoadHistory} has reading date {String:reading_date}")
LoadHistory.load_mw = model.Property(f"{LoadHistory} has load {Float:load_mw} MW")
LoadHistory.temperature_f = model.Property(f"{LoadHistory} has temperature {Float:temperature_f} F")
LoadHistory.is_peak_season = model.Property(f"{LoadHistory} is peak season {Boolean:is_peak_season}")
LoadHistory.substation = model.Relationship(f"{LoadHistory} measured at {Substation}")

# DCAnnouncement
DCAnnouncement = model.Concept("DCAnnouncement", identify_by={"id": String})
DCAnnouncement.hyperscaler = model.Property(
    f"{DCAnnouncement} from hyperscaler {String:hyperscaler}")
DCAnnouncement.announced_date = model.Property(
    f"{DCAnnouncement} announced on {String:announced_date}")
DCAnnouncement.announced_mw = model.Property(f"{DCAnnouncement} announcing {Float:announced_mw} MW")
DCAnnouncement.substation = model.Relationship(f"{DCAnnouncement} targets {Substation}")

# --------------------------------------------------
# Load CSV data into ontology
# --------------------------------------------------

# Load substation data from CSV.
src = model.data(substations_df)
model.define(Substation.new(
    id=src.ID, name=src.NAME, voltage_kv=src.VOLTAGE_KV,
    max_capacity_mw=src.MAX_CAPACITY_MW, current_load_mw=src.CURRENT_LOAD_MW,
    latitude=src.LATITUDE, longitude=src.LONGITUDE,
))

# Load generator data from CSV.
src = model.data(generators_df)
model.define(Generator.new(
    id=src.ID, name=src.NAME, gen_type=src.GEN_TYPE,
    capacity_mw=src.CAPACITY_MW, min_output_mw=src.MIN_OUTPUT_MW,
    ramp_rate_mw_per_hr=src.RAMP_RATE_MW_PER_HR, startup_cost=src.STARTUP_COST,
    marginal_cost=src.MARGINAL_COST, min_up_time_hrs=src.MIN_UP_TIME_HRS,
    min_down_time_hrs=src.MIN_DOWN_TIME_HRS, emissions_rate=src.EMISSIONS_RATE,
    is_renewable=src.IS_RENEWABLE,
    substation=Substation.filter_by(id=src.SUBSTATION_ID),
))

# Load transmission line data from CSV.
src = model.data(transmission_lines_df)
model.define(TransmissionLine.new(
    id=src.ID,
    from_substation=Substation.filter_by(id=src.FROM_SUBSTATION_ID),
    to_substation=Substation.filter_by(id=src.TO_SUBSTATION_ID),
    capacity_mw=src.CAPACITY_MW, length_km=src.LENGTH_KM,
    impedance=src.IMPEDANCE, is_active=src.IS_ACTIVE,
    maintenance_priority=src.MAINTENANCE_PRIORITY,
))

# Load load zone data from CSV.
src = model.data(load_zones_df)
model.define(LoadZone.new(
    id=src.ID, name=src.NAME,
    peak_demand_mw=src.PEAK_DEMAND_MW, base_demand_mw=src.BASE_DEMAND_MW,
))

# Load demand period data from CSV.
src = model.data(demand_periods_df)
model.define(DemandPeriod.new(
    id=src.ID, load_zone=LoadZone.filter_by(id=src.LOAD_ZONE_ID),
    period=src.PERIOD, demand_mw=src.DEMAND_MW, price_per_mwh=src.PRICE_PER_MWH,
))

# Load renewable profile data from CSV.
src = model.data(renewable_profiles_df)
model.define(RenewableProfile.new(
    id=src.ID, generator=Generator.filter_by(id=src.GENERATOR_ID),
    period=src.PERIOD, capacity_factor=src.CAPACITY_FACTOR,
))

# Load maintenance window data from CSV.
src = model.data(maintenance_windows_df)
model.define(MaintenanceWindow.new(
    id=src.ID, asset_type=src.ASSET_TYPE, asset_id=src.ASSET_ID,
    start_period=src.START_PERIOD, end_period=src.END_PERIOD,
    is_planned=src.IS_PLANNED,
))

# Load customer data from CSV.
src = model.data(customers_df)
model.define(Customer.new(
    id=src.ID, name=src.NAME, load_zone=LoadZone.filter_by(id=src.LOAD_ZONE_ID),
    contracted_demand_mw=src.CONTRACTED_DEMAND_MW, flexibility_pct=src.FLEXIBILITY_PCT,
    curtailment_cost_per_mwh=src.CURTAILMENT_COST_PER_MWH,
))

# Load data center request data from CSV.
src = model.data(data_center_requests_df)
model.define(DataCenterRequest.new(
    id=src.ID, name=src.NAME, hyperscaler=src.HYPERSCALER,
    requested_mw=src.REQUESTED_MW,
    substation=Substation.filter_by(id=src.SUBSTATION_ID),
    annual_revenue_per_mw=src.ANNUAL_REVENUE_PER_MW,
    pue=src.PUE, is_ai_workload=src.IS_AI_WORKLOAD,
    cooling_type=src.COOLING_TYPE,
    low_carbon_requirement_pct=src.LOW_CARBON_REQUIREMENT_PCT,
    queue_position=src.QUEUE_POSITION, status=src.STATUS,
))

# Load substation upgrade data from CSV.
src = model.data(substation_upgrades_df)
model.define(SubstationUpgrade.new(
    id=src.ID, substation=Substation.filter_by(id=src.SUBSTATION_ID),
    capacity_increase_mw=src.CAPACITY_INCREASE_MW, cost_million=src.COST_MILLION,
    lead_time_months=src.LEAD_TIME_MONTHS, enables_low_carbon=src.ENABLES_LOW_CARBON,
))

# Load demand forecast data from CSV.
src = model.data(demand_forecasts_df)
model.define(DemandForecast.new(
    id=src.ID, substation=Substation.filter_by(id=src.SUBSTATION_ID),
    forecast_period=src.FORECAST_PERIOD, predicted_load_mw=src.PREDICTED_LOAD_MW,
    confidence=src.CONFIDENCE, includes_dc_growth=src.INCLUDES_DC_GROWTH,
))

# Load history data from CSV.
load_history_df["IS_PEAK_SEASON"] = load_history_df["IS_PEAK_SEASON"].astype(bool)
load_history_df["READING_ID"] = load_history_df["READING_ID"].astype(str)
src = model.data(load_history_df)
model.define(LoadHistory.new(
    id=src.READING_ID, reading_date=src.READING_DATE, load_mw=src.LOAD_MW,
    temperature_f=src.TEMPERATURE_F, is_peak_season=src.IS_PEAK_SEASON,
    substation=Substation.filter_by(id=src.SUBSTATION_ID),
))

# Load DC announcement data from CSV.
src = model.data(dc_announcements_df)
model.define(DCAnnouncement.new(
    id=src.ANNOUNCEMENT_ID, hyperscaler=src.HYPERSCALER,
    announced_date=src.ANNOUNCED_DATE, announced_mw=src.ANNOUNCED_MW,
    substation=Substation.filter_by(id=src.SUBSTATION_ID),
))

# --------------------------------------------------
# Stage 1: Predict -- Substation Load Forecasting
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 1: PREDICT -- Substation Load Forecasting")
print("=" * 60)

# Try loading a pre-trained GNN from the model registry.
# If not available, fall back to reading the demand_forecasts CSV directly.
gnn_available = False
try:
    from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

    gnn_graph = Graph(model, directed=False, weighted=True, aggregator="sum")

    SubRef = Substation.ref()
    line_ref = TransmissionLine.ref()
    s1, s2 = Substation.ref(), Substation.ref()

    gnn = GNN(
        database="ENERGY",
        schema="PUBLIC",
        exp_database="ENERGY",
        exp_schema="EXPERIMENTS",
        graph=gnn_graph,
        pt=PropertyTransformer(
            continuous=[Substation.max_capacity_mw, Substation.current_load_mw],
            drop=[Substation, TransmissionLine],
        ),
        model_database="ENERGY",
        model_schema="MODEL_REGISTRY",
        model_name="substation_load_forecaster",
        version_name="v1.0",
    )
    gnn.load()
    gnn_available = True
    print("  GNN model loaded from ENERGY.MODEL_REGISTRY")
except Exception as e:
    print(
        f"  GNN model not available ({type(e).__name__}), falling back to DEMAND_FORECASTS table"
    )

# ── Ontology enrichment: write predicted load back to Substation ──────────────
# This is the first link in the accretive chain: Stage 3 rules and Stage 4
# optimization both consume predicted_load instead of static current_load.
Substation.predicted_load = model.Property(f"{Substation} has {Float:predicted_load}")
model.define(
    Substation.predicted_load(
        aggs.max(DemandForecast.predicted_load_mw)
        .where(DemandForecast.substation(Substation))
        .per(Substation)
    )
)

if gnn_available:
    print("  GNN model loaded -- predictions would be materialized here.")

# Query demand forecasts for structured enrichments.
DemandForecast_ref = DemandForecast.ref()
SubRef = Substation.ref()
forecast_df = (
    model.select(
        SubRef.id.alias("sub_id"),
        SubRef.name.alias("sub_name"),
        SubRef.current_load_mw.alias("current_load"),
        SubRef.max_capacity_mw.alias("max_capacity"),
        DemandForecast_ref.forecast_period.alias("forecast_period"),
        DemandForecast_ref.predicted_load_mw.alias("predicted_load"),
        DemandForecast_ref.confidence.alias("confidence"),
    )
    .where(DemandForecast_ref.substation(SubRef))
    .to_df()
)

if len(forecast_df) > 0:
    forecast_df["predicted_load"] = forecast_df["predicted_load"].astype(float)
    forecast_df["current_load"] = forecast_df["current_load"].astype(float)
    forecast_df["max_capacity"] = forecast_df["max_capacity"].astype(float)
    forecast_df["forecast_period"] = forecast_df["forecast_period"].astype(int)

    sub_forecast = (
        forecast_df.groupby(["sub_id", "sub_name", "current_load", "max_capacity"])
        .agg(
            predicted_load=("predicted_load", "max"),
            min_breach_period=("forecast_period", "min"),
        )
        .reset_index()
    )

    sub_forecast["growth_rate"] = (
        sub_forecast["predicted_load"] - sub_forecast["current_load"]
    ) / sub_forecast["current_load"].clip(lower=0.1)

    breach_df = forecast_df[forecast_df["predicted_load"] > forecast_df["max_capacity"]]
    breach_months = breach_df.groupby("sub_id")["forecast_period"].min().reset_index()
    breach_months.columns = ["sub_id", "breach_months"]

    sub_forecast = sub_forecast.merge(breach_months, on="sub_id", how="left")
    sub_forecast["breach_months"] = (
        sub_forecast["breach_months"].fillna(999).astype(int)
    )

    at_risk = sub_forecast[sub_forecast["breach_months"] < 999].sort_values("breach_months")
    print("\n  Substations at risk of capacity breach:")
    print(
        f"  {'Substation':<25} {'Current':>10} {'Predicted':>10} {'Max Cap':>10} {'Breach Mo':>10} {'Growth':>8}"
    )
    print(f"  {'-' * 73}")
    for _, r in at_risk.iterrows():
        print(
            f"  {r['sub_name']:<25} {r['current_load']:>10.1f} {r['predicted_load']:>10.1f} "
            f"{r['max_capacity']:>10.1f} {r['breach_months']:>10} {r['growth_rate']:>7.1%}"
        )

    if len(at_risk) == 0:
        print("  (none predicted within forecast horizon)")

    print("\n  All substation forecasts:")
    for _, r in sub_forecast.sort_values("predicted_load", ascending=False).iterrows():
        breach_str = f"{r['breach_months']}mo" if r["breach_months"] < 999 else "safe"
        print(
            f"    {r['sub_name']:<25} pred={r['predicted_load']:.1f} MW  growth={r['growth_rate']:.1%}  breach={breach_str}"
        )
else:
    print(
        "  No demand forecasts available -- Stage 1 outputs will use current_load as fallback"
    )
    sub_forecast = pd.DataFrame()

# --------------------------------------------------
# Stage 2: Graph -- Grid Topology & Structural Vulnerability
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 2: GRAPH -- Grid Topology & Structural Vulnerability")
print("=" * 60)

grid_graph = Graph(
    model,
    directed=False,
    weighted=False,
    node_concept=Substation,
    aggregator="sum",
)

# Edges: active transmission lines between substations.
line_ref = TransmissionLine.ref()
model.define(grid_graph.Edge.new(src=line_ref.from_substation, dst=line_ref.to_substation)).where(
    line_ref.is_active == True
)

# a) Weakly Connected Components
wcc = grid_graph.weakly_connected_component()
node_ref = grid_graph.Node.ref("n")
comp_ref = grid_graph.Node.ref("comp")

wcc_df = (
    model.where(wcc(node_ref, comp_ref))
    .select(
        node_ref.id.alias("substation_id"),
        node_ref.name.alias("substation_name"),
        comp_ref.id.alias("component_id"),
        aggs.count(node_ref).per(comp_ref).alias("component_size"),
    )
    .to_df()
)

num_components = wcc_df["component_id"].nunique()
total_substations = len(wcc_df)
print(
    f"\n  Grid connectivity: {total_substations} substations, {num_components} component(s)"
)
if num_components == 1:
    print("  CONNECTED: All substations reachable from any other.")
else:
    print(f"  FRAGMENTED: {num_components} isolated grid segments detected!")

# b) Community Detection (Louvain)
community = grid_graph.louvain()
comm_label = Integer.ref("comm")

# c) Centrality Analysis (betweenness, degree, eigenvector)
betweenness = grid_graph.betweenness_centrality()
btwn_score = Float.ref("btwn")

degree = grid_graph.degree_centrality()
deg_score = Float.ref("deg")

eigenvector = grid_graph.eigenvector_centrality()
eig_score = Float.ref("eig")

# Store graph results directly on Substation.
Substation.grid_community = model.Property(
    f"{Substation} in grid community {Integer:grid_community}"
)
Substation.betweenness = model.Property(f"{Substation} has {Float:betweenness}")
Substation.degree_centrality = model.Property(f"{Substation} has {Float:degree_centrality}")
Substation.eigenvector_centrality = model.Property(
    f"{Substation} has {Float:eigenvector_centrality}"
)

sub_ref = Substation.ref()
model.define(sub_ref.grid_community(comm_label)).where(community(sub_ref, comm_label))
model.define(sub_ref.betweenness(btwn_score)).where(betweenness(sub_ref, btwn_score))
model.define(sub_ref.degree_centrality(deg_score)).where(degree(sub_ref, deg_score))
model.define(sub_ref.eigenvector_centrality(eig_score)).where(eigenvector(sub_ref, eig_score))

# Composite critical rank from all three centrality metrics.
Substation.betweenness_rank = model.Property(f"{Substation} has {Integer:betweenness_rank}")
Substation.degree_rank = model.Property(f"{Substation} has {Integer:degree_rank}")
Substation.eigenvector_rank = model.Property(f"{Substation} has {Integer:eigenvector_rank}")
Substation.combined_rank = model.Property(f"{Substation} has {Integer:combined_rank}")
Substation.critical_rank = model.Property(f"{Substation} has {Integer:critical_rank}")

model.define(
    Substation.betweenness_rank(aggs.rank(aggs.desc(Substation.betweenness, Substation.id)))
)
model.define(
    Substation.degree_rank(aggs.rank(aggs.desc(Substation.degree_centrality, Substation.id)))
)
model.define(
    Substation.eigenvector_rank(
        aggs.rank(aggs.desc(Substation.eigenvector_centrality, Substation.id))
    )
)
model.define(
    Substation.combined_rank(
        Substation.betweenness_rank + Substation.degree_rank + Substation.eigenvector_rank
    )
)
model.define(Substation.critical_rank(aggs.rank(Substation.combined_rank, Substation.id)))

Substation.is_structurally_critical = model.Relationship(f"{Substation} is structurally critical")
model.where(Substation.critical_rank <= CRITICAL_THRESHOLD).define(
    Substation.is_structurally_critical()
)

community_df = model.select(
    Substation.id.alias("substation_id"),
    Substation.name.alias("name"),
    Substation.grid_community.alias("community"),
).to_df()
community_df["community"] = community_df["community"].astype(int)

num_communities = community_df["community"].nunique()
print(f"\n  Grid community structure (Louvain): {num_communities} region(s)")
for comm_id, group in community_df.groupby("community"):
    members = ", ".join(group["name"].tolist())
    print(f"    Region {comm_id}: {members}")

centrality_df = (
    model.select(
        Substation.id.alias("substation_id"),
        Substation.name.alias("name"),
        Substation.betweenness.alias("betweenness"),
        Substation.degree_centrality.alias("degree_centrality"),
        Substation.eigenvector_centrality.alias("eigenvector_centrality"),
        Substation.critical_rank.alias("critical_rank"),
    )
    .to_df()
    .sort_values("critical_rank")
    .reset_index(drop=True)
)
centrality_df["critical_rank"] = centrality_df["critical_rank"].astype(int)

print(f"\n  All substations by centrality (top {CRITICAL_THRESHOLD} marked CRITICAL):")
for i, (_, row) in enumerate(centrality_df.iterrows(), 1):
    flag = " [CRITICAL]" if row["critical_rank"] <= CRITICAL_THRESHOLD else ""
    print(
        f"    #{i}: {row['name']} (betw={row['betweenness']:.4f}, "
        f"deg={row['degree_centrality']:.4f}, eig={row['eigenvector_centrality']:.4f}){flag}"
    )

# Cross-reference: DC-targeted substations that are ALSO critical bottlenecks
DCRef = DataCenterRequest.ref()
SubRef2 = Substation.ref()
dc_sub_df = (
    model.where(DCRef.substation(SubRef2))
    .select(
        DCRef.name.alias("dc_name"),
        DCRef.requested_mw.alias("requested_mw"),
        SubRef2.id.alias("sub_id"),
        SubRef2.name.alias("sub_name"),
    )
    .to_df()
)

if len(dc_sub_df) > 0 and len(centrality_df) > 0:
    critical_ids = centrality_df.loc[
        centrality_df["critical_rank"] <= CRITICAL_THRESHOLD, "substation_id"
    ]
    dc_at_bottleneck = dc_sub_df[dc_sub_df["sub_id"].isin(critical_ids)]
    if len(dc_at_bottleneck) > 0:
        print(
            "\n  KEY INSIGHT: DC requests targeting structurally critical substations:"
        )
        for _, row in dc_at_bottleneck.iterrows():
            print(
                f"    {row['dc_name']} ({row['requested_mw']} MW) -> {row['sub_name']} [CRITICAL]"
            )
    else:
        print("\n  No DC requests target structurally critical substations.")

# --------------------------------------------------
# Stage 3: Rules -- Interconnection Queue Compliance
# --------------------------------------------------
# Accretive chain: each rule consumes ontology enrichments from earlier stages.
# Rule 1 reads Substation.predicted_load (Stage 1).
# Rule 2 reads Substation.is_structurally_critical (Stage 2).
# Rule 3 reads Generator.emissions_rate (base data) to derive low-carbon capacity.
# All flags are written back as Relationships — queryable and consumable downstream.

print(f"\n{'=' * 60}")
print("STAGE 3: RULES -- Interconnection Queue Compliance")
print("=" * 60)

# Rule 1: Capacity check -- consumes predicted_load from Stage 1
DataCenterRequest.fails_capacity = model.Relationship(f"{DataCenterRequest} fails capacity check")
SubRef_rule = Substation.ref()
effective_load_rule = SubRef_rule.predicted_load | SubRef_rule.current_load_mw
model.where(
    DataCenterRequest.substation(SubRef_rule),
    DataCenterRequest.requested_mw + effective_load_rule > SubRef_rule.max_capacity_mw,
).define(DataCenterRequest.fails_capacity())

# Rule 2: Structural risk -- uses centrality-based criticality from Stage 2
DataCenterRequest.fails_structural = model.Relationship(f"{DataCenterRequest} fails structural risk check")
SubRef_sr = Substation.ref()
model.where(
    DataCenterRequest.substation(SubRef_sr),
    SubRef_sr.is_structurally_critical(),
).define(DataCenterRequest.fails_structural())

# Rule 3: Low-carbon mandate -- check if DC's low-carbon requirement can be met
# Low-carbon = zero-emission generation (renewable + nuclear), keyed on emissions_rate == 0
Substation.low_carbon_gen_mw = model.Property(f"{Substation} has {Float:low_carbon_gen_mw}")
Substation.total_gen_mw = model.Property(f"{Substation} has {Float:total_gen_mw}")
model.define(
    Substation.low_carbon_gen_mw(
        aggs.sum(Generator.capacity_mw)
        .where(Generator.substation(Substation), Generator.emissions_rate == 0.0)
        .per(Substation)
    )
)
model.define(
    Substation.total_gen_mw(
        aggs.sum(Generator.capacity_mw)
        .where(Generator.substation(Substation))
        .per(Substation)
    )
)

DataCenterRequest.fails_low_carbon = model.Relationship(f"{DataCenterRequest} fails low-carbon mandate")
SubRef_lc = Substation.ref()
model.where(
    DataCenterRequest.substation(SubRef_lc),
    (SubRef_lc.low_carbon_gen_mw | 0.0) * 100 < DataCenterRequest.low_carbon_requirement_pct * (SubRef_lc.total_gen_mw | 0.001),
).define(DataCenterRequest.fails_low_carbon())

# Composite: compliant if none of the checks fail
DataCenterRequest.is_compliant = model.Relationship(f"{DataCenterRequest} is compliant")
model.where(
    model.not_(DataCenterRequest.fails_capacity()),
    model.not_(DataCenterRequest.fails_structural()),
    model.not_(DataCenterRequest.fails_low_carbon()),
).define(DataCenterRequest.is_compliant())

# Query rule outputs for compliance summary
compliance_df = (
    model.select(
        DataCenterRequest.id.alias("dc_id"),
        DataCenterRequest.name.alias("dc_name"),
        DataCenterRequest.hyperscaler.alias("hyperscaler"),
        DataCenterRequest.queue_position.alias("queue_pos"),
        DataCenterRequest.requested_mw.alias("requested_mw"),
    )
    .to_df()
    .sort_values("queue_pos")
)


def _query_flag(relationship, flag_name):
    df = model.where(relationship()).select(
        DataCenterRequest.id.alias("dc_id"),
    ).to_df()
    if len(df) > 0:
        df[flag_name] = "FAIL"
    else:
        df = pd.DataFrame(columns=["dc_id", flag_name])
    return df


cap_fail_df = _query_flag(DataCenterRequest.fails_capacity, "capacity_flag")
struct_fail_df = _query_flag(DataCenterRequest.fails_structural, "structural_flag")
lc_fail_df = _query_flag(DataCenterRequest.fails_low_carbon, "low_carbon_flag")

compliant_ids_df = model.where(DataCenterRequest.is_compliant()).select(
    DataCenterRequest.id.alias("dc_id"),
).to_df()
if len(compliant_ids_df) > 0:
    compliant_ids_df["is_compliant"] = "Y"
else:
    compliant_ids_df = pd.DataFrame(columns=["dc_id", "is_compliant"])

compliance_df = compliance_df.merge(cap_fail_df, on="dc_id", how="left")
compliance_df["capacity_flag"] = compliance_df["capacity_flag"].fillna("PASS")
compliance_df = compliance_df.merge(struct_fail_df, on="dc_id", how="left")
compliance_df["structural_flag"] = compliance_df["structural_flag"].fillna("PASS")
compliance_df = compliance_df.merge(lc_fail_df, on="dc_id", how="left")
compliance_df["low_carbon_flag"] = compliance_df["low_carbon_flag"].fillna("PASS")
compliance_df = compliance_df.merge(compliant_ids_df, on="dc_id", how="left")
compliance_df["is_compliant"] = compliance_df["is_compliant"].fillna("N")

num_dc = len(compliance_df)
print(f"\n  Evaluating {num_dc} DC requests against 3 declarative compliance rules...")

print(
    f"\n  {'DC Request':<25} {'Hyper':<12} {'Q#':>3} {'MW':>6} "
    f"{'Cap':>5} {'LowC':>5} {'Crit':>5} {'OK?':>4}"
)
print(f"  {'-' * 70}")
for _, r in compliance_df.iterrows():
    print(
        f"  {r['dc_name']:<25} {r['hyperscaler']:<12} {r['queue_pos']:>3} {float(r['requested_mw']):>6.0f} "
        f"{r['capacity_flag']:>5} {r['low_carbon_flag']:>5} "
        f"{r['structural_flag']:>5} {r['is_compliant']:>4}"
    )

compliant_count = len(compliance_df[compliance_df["is_compliant"] == "Y"])
flagged_count = len(compliance_df[compliance_df["is_compliant"] == "N"])
print(
    f"\n  Summary: {compliant_count} compliant, {flagged_count} flagged (out of {num_dc} requests)"
)

# --------------------------------------------------
# Stage 4: Optimize -- Joint DC Approval + Grid Upgrade
#   Accretive chain: the capacity constraint uses predicted_load from Stage 1
#   (via the | fallback pattern), matching the rules engine. All solve results
#   (x_approve, x_upgrade per InvestmentLevel) are written to the ontology —
#   queryable via model.select(), not parsed from solver output.
#   One solve across 5 InvestmentLevel scenarios produces the Pareto frontier.
# --------------------------------------------------

print(f"\n{'=' * 60}")
print("STAGE 4: OPTIMIZE -- Joint Interconnection + Upgrade")
print("=" * 60)

# InvestmentLevel Scenario Concept: 5 budget levels
InvestmentLevel = model.Concept("InvestmentLevel", identify_by={"name": String})
InvestmentLevel.budget_cap = model.Property(f"{InvestmentLevel} has {Float:budget_cap}")

inv_data = model.data(pd.DataFrame([
    {"name": "$200M", "budget_cap": 200.0},
    {"name": "$300M", "budget_cap": 300.0},
    {"name": "$400M", "budget_cap": 400.0},
    {"name": "$500M", "budget_cap": 500.0},
    {"name": "$600M", "budget_cap": 600.0},
]))
model.define(InvestmentLevel.new(inv_data.to_schema()))

# Decision variables indexed by InvestmentLevel
DataCenterRequest.x_approve = model.Property(
    f"{DataCenterRequest} in {InvestmentLevel} has {Float:x_approve}"
)
SubstationUpgrade.x_upgrade = model.Property(
    f"{SubstationUpgrade} in {InvestmentLevel} has {Float:x_upgrade}"
)

# Float refs for variable binding in constraints/objective
x_a = Float.ref("xa")
x_u = Float.ref("xu")

# Refs for aggregation joins
DCRef = DataCenterRequest.ref()
UpgRef = SubstationUpgrade.ref()

# Problem formulation
p = Problem(model, Float)

p.solve_for(DataCenterRequest.x_approve(InvestmentLevel, x_a), type="bin",
            name=["approve", InvestmentLevel.name, DataCenterRequest.id])
p.solve_for(SubstationUpgrade.x_upgrade(InvestmentLevel, x_u), type="bin",
            name=["upgrade", InvestmentLevel.name, SubstationUpgrade.id])

# C1: Substation capacity per investment level
# Uses predicted_load from Stage 1 (with current_load fallback) — the accretive chain.
x_a_c = Float.ref("xa_c")
x_u_c = Float.ref("xu_c")
effective_load = Substation.predicted_load | Substation.current_load_mw

p.satisfy(model.where(
    DataCenterRequest.x_approve(InvestmentLevel, x_a_c),
    SubstationUpgrade.x_upgrade(InvestmentLevel, x_u_c),
    DataCenterRequest.substation(Substation),
    SubstationUpgrade.substation(Substation),
).require(
    Substation.max_capacity_mw - effective_load
    + sum(x_u_c * UpgRef.capacity_increase_mw).where(
        UpgRef.substation == Substation).per(Substation, InvestmentLevel)
    >= sum(x_a_c * DCRef.requested_mw).where(
        DCRef.substation == Substation).per(Substation, InvestmentLevel)
))

# C2: Budget per investment level
p.satisfy(model.where(
    SubstationUpgrade.x_upgrade(InvestmentLevel, x_u),
).require(
    sum(x_u * SubstationUpgrade.cost_million).per(InvestmentLevel) <= InvestmentLevel.budget_cap
))

# Objective: maximize total DC revenue across all levels
p.maximize(
    sum(x_a * DataCenterRequest.annual_revenue_per_mw * DataCenterRequest.requested_mw).where(
        DataCenterRequest.x_approve(InvestmentLevel, x_a)
    )
)

# Solve
print("\n  Solving across 5 investment levels ($200M-$600M)...")
p.solve("highs", time_limit_sec=120)
si = p.solve_info()
print(f"  Status: {si.termination_status}")
print(f"  Objective: {float(si.objective_value):,.2f}")

# --------------------------------------------------
# Results -- Pareto Frontier from Ontology
# --------------------------------------------------

# Approved DCs per level
print("\n  PARETO FRONTIER (queried from ontology):")
print("\n  Approved DCs per investment level:")
model.select(
    InvestmentLevel.name.alias("level"),
    DataCenterRequest.name.alias("dc"),
    DataCenterRequest.requested_mw.alias("mw"),
    x_a.alias("approved"),
).where(
    DataCenterRequest.x_approve(InvestmentLevel, x_a), x_a > 0.5
).inspect()

# Revenue and cost per level
rev_per_level = sum(x_a * DataCenterRequest.annual_revenue_per_mw * DataCenterRequest.requested_mw).per(
    InvestmentLevel
).where(DataCenterRequest.x_approve(InvestmentLevel, x_a))

cost_per_level = sum(x_u * SubstationUpgrade.cost_million).per(
    InvestmentLevel
).where(SubstationUpgrade.x_upgrade(InvestmentLevel, x_u))

print("\n  Revenue and upgrade cost by investment level:")
model.select(
    InvestmentLevel.name.alias("level"),
    InvestmentLevel.budget_cap.alias("budget_cap"),
    rev_per_level.alias("revenue"),
    cost_per_level.alias("upgrade_cost"),
).inspect()

# Per-level detail via pandas
x_q = Float.ref()
dc_approval_df = (
    model.where(DataCenterRequest.x_approve(InvestmentLevel, x_q), x_q > 0.5)
    .select(
        InvestmentLevel.name.alias("level"),
        InvestmentLevel.budget_cap.alias("budget"),
        DataCenterRequest.id.alias("dc_id"),
        DataCenterRequest.name.alias("dc_name"),
        DataCenterRequest.hyperscaler.alias("hyperscaler"),
        DataCenterRequest.requested_mw.alias("requested_mw"),
        DataCenterRequest.annual_revenue_per_mw.alias("rev_per_mw"),
    )
    .to_df()
)

x_uq = Float.ref()
upgrade_result_df = (
    model.where(SubstationUpgrade.x_upgrade(InvestmentLevel, x_uq), x_uq > 0.5)
    .select(
        InvestmentLevel.name.alias("level"),
        SubstationUpgrade.id.alias("upgrade_id"),
        SubstationUpgrade.capacity_increase_mw.alias("capacity_mw"),
        SubstationUpgrade.cost_million.alias("cost_m"),
    )
    .to_df()
)

# Build Pareto frontier table
investment_levels_df = model.select(
    InvestmentLevel.name.alias("level"),
    InvestmentLevel.budget_cap.alias("budget"),
).to_df().sort_values("budget")

pareto_rows = []
for _, lvl in investment_levels_df.iterrows():
    level_name = lvl["level"]
    budget = float(lvl["budget"])

    level_dcs = dc_approval_df[dc_approval_df["level"] == level_name] if len(dc_approval_df) > 0 else pd.DataFrame()
    n_approved = len(level_dcs)
    total_mw = float(level_dcs["requested_mw"].astype(float).sum()) if n_approved > 0 else 0
    total_rev = float(
        (level_dcs["requested_mw"].astype(float) * level_dcs["rev_per_mw"].astype(float)).sum()
    ) if n_approved > 0 else 0

    level_upg = upgrade_result_df[upgrade_result_df["level"] == level_name] if len(upgrade_result_df) > 0 else pd.DataFrame()
    n_upgrades = len(level_upg)
    upgrade_cost = float(level_upg["cost_m"].astype(float).sum()) if n_upgrades > 0 else 0
    upgrade_mw = float(level_upg["capacity_mw"].astype(float).sum()) if n_upgrades > 0 else 0

    net_value = total_rev - (upgrade_cost * 1e6 / AMORTIZATION_YEARS)

    pareto_rows.append({
        "level": level_name,
        "budget": budget,
        "n_approved": n_approved,
        "total_mw": total_mw,
        "revenue": total_rev,
        "n_upgrades": n_upgrades,
        "upgrade_cost_m": upgrade_cost,
        "upgrade_mw": upgrade_mw,
        "net_value": net_value,
    })

# Print Pareto frontier
print(
    f"\n  {'#':>3} {'Level':>8} {'Budget $M':>10} {'DCs':>5} {'DC MW':>8} "
    f"{'Revenue $/yr':>14} {'Upg $M':>8} {'Upg MW':>8} {'Net Value':>14}"
)
print(f"  {'-' * 85}")
for j, pt in enumerate(pareto_rows):
    print(
        f"  {j + 1:>3} {pt['level']:>8} {pt['budget']:>10,.0f} "
        f"{pt['n_approved']:>5} {pt['total_mw']:>8,.0f} "
        f"{pt['revenue']:>14,.0f} {pt['upgrade_cost_m']:>8,.1f} "
        f"{pt['upgrade_mw']:>8,.1f} {pt['net_value']:>14,.0f}"
    )

# Detailed results per investment level
for pt in pareto_rows:
    level_name = pt["level"]
    print(f"\n  --- {level_name} (Budget: ${pt['budget']:,.0f}M) ---")
    print(f"  Net value: ${pt['net_value']:,.0f}")

    level_dcs = dc_approval_df[dc_approval_df["level"] == level_name] if len(dc_approval_df) > 0 else pd.DataFrame()
    print(f"\n  Approved Data Centers: {pt['n_approved']}")
    print(f"  Total MW: {pt['total_mw']:,.1f} | Revenue: ${pt['revenue']:,.0f}/yr")
    if len(level_dcs) > 0:
        for _, row in level_dcs.iterrows():
            print(
                f"    {row['dc_name']} ({row['hyperscaler']}): "
                f"{float(row['requested_mw']):.0f} MW, "
                f"${float(row['requested_mw']) * float(row['rev_per_mw']):,.0f}/yr"
            )

    level_upg = upgrade_result_df[upgrade_result_df["level"] == level_name] if len(upgrade_result_df) > 0 else pd.DataFrame()
    print(f"\n  Selected Upgrades: {pt['n_upgrades']} (${pt['upgrade_cost_m']:,.1f}M, +{pt['upgrade_mw']:,.1f} MW)")
    if len(level_upg) > 0:
        for _, row in level_upg.iterrows():
            print(f"    {row['upgrade_id']}: +{float(row['capacity_mw']):.0f} MW, ${float(row['cost_m']):.1f}M")

# Marginal analysis + knee detection
if len(pareto_rows) >= 3:
    print("\n  MARGINAL ANALYSIS (value gained per additional $M budget):")
    rates = []
    for j in range(len(pareto_rows) - 1):
        d_val = pareto_rows[j + 1]["net_value"] - pareto_rows[j]["net_value"]
        d_budget = pareto_rows[j + 1]["budget"] - pareto_rows[j]["budget"]
        rate = d_val / d_budget if abs(d_budget) > 1e-6 else 0
        rates.append(rate)
        d_mw = pareto_rows[j + 1]["total_mw"] - pareto_rows[j]["total_mw"]
        d_dcs = pareto_rows[j + 1]["n_approved"] - pareto_rows[j]["n_approved"]
        print(
            f"    {pareto_rows[j]['level']:>6} -> {pareto_rows[j+1]['level']:<6}: "
            f"dValue={d_val:>+14,.0f}, dBudget={d_budget:>+6,.0f}$M, "
            f"dMW={d_mw:>+8,.0f}, dDCs={d_dcs:>+3}, "
            f"marginal={rate:>+12,.0f}$/M$"
        )

    if len(rates) >= 2:
        max_jump, knee_idx = 0, 1
        for j in range(len(rates) - 1):
            if abs(rates[j + 1]) > 1e-6:
                jump = abs(rates[j] / rates[j + 1])
            elif abs(rates[j]) > 1e-6:
                jump = float("inf")
            else:
                jump = 0
            if jump > max_jump:
                max_jump = jump
                knee_idx = j + 1

        knee = pareto_rows[knee_idx]
        print(
            f"\n  KNEE POINT: {knee['level']} -- ${knee['budget']:,.0f}M budget, "
            f"${knee['net_value']:,.0f} net value, {knee['n_approved']} DCs, "
            f"{knee['total_mw']:,.0f} MW"
        )
        print("  Diminishing returns beyond this investment level.")

# --------------------------------------------------
# Final Summary
# --------------------------------------------------

print(f"\n{'=' * 80}")
print("  PIPELINE COMPLETE: 4 stages executed on shared Energy Grid ontology")
print("  Stage 4 solved all investment levels in a single formulation")
print("  (Scenario Concept pattern -- results in ontology, no re-solve loops)")
print("=" * 80)
