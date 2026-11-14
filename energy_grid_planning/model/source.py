"""Bundled grid CSVs and the investment levels, loaded into the shared model."""

from pathlib import Path

import pandas as pd

from .schema import (
    Customer,
    DataCenterRequest,
    DCAnnouncement,
    DemandForecast,
    DemandPeriod,
    Generator,
    InvestmentLevel,
    LoadHistory,
    LoadZone,
    MaintenanceWindow,
    RenewableProfile,
    Substation,
    SubstationUpgrade,
    TransmissionLine,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --------------------------------------------------
# CSV loader with boolean auto-detection
# --------------------------------------------------

def load_csv(filename):
    df = pd.read_csv(DATA_DIR / filename)
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
    substation=Substation.lookup(id=src.SUBSTATION_ID),
))

# Load transmission line data from CSV.
src = model.data(transmission_lines_df)
model.define(TransmissionLine.new(
    id=src.ID,
    from_substation=Substation.lookup(id=src.FROM_SUBSTATION_ID),
    to_substation=Substation.lookup(id=src.TO_SUBSTATION_ID),
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
    id=src.ID, load_zone=LoadZone.lookup(id=src.LOAD_ZONE_ID),
    period=src.PERIOD, demand_mw=src.DEMAND_MW, price_per_mwh=src.PRICE_PER_MWH,
))

# Load renewable profile data from CSV.
src = model.data(renewable_profiles_df)
model.define(RenewableProfile.new(
    id=src.ID, generator=Generator.lookup(id=src.GENERATOR_ID),
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
    id=src.ID, name=src.NAME, load_zone=LoadZone.lookup(id=src.LOAD_ZONE_ID),
    contracted_demand_mw=src.CONTRACTED_DEMAND_MW, flexibility_pct=src.FLEXIBILITY_PCT,
    curtailment_cost_per_mwh=src.CURTAILMENT_COST_PER_MWH,
))

# Load data center request data from CSV.
src = model.data(data_center_requests_df)
model.define(DataCenterRequest.new(
    id=src.ID, name=src.NAME, hyperscaler=src.HYPERSCALER,
    requested_mw=src.REQUESTED_MW,
    substation=Substation.lookup(id=src.SUBSTATION_ID),
    annual_revenue_per_mw=src.ANNUAL_REVENUE_PER_MW,
    pue=src.PUE, is_ai_workload=src.IS_AI_WORKLOAD,
    cooling_type=src.COOLING_TYPE,
    low_carbon_requirement_pct=src.LOW_CARBON_REQUIREMENT_PCT,
    queue_position=src.QUEUE_POSITION, status=src.STATUS,
))

# Load substation upgrade data from CSV.
src = model.data(substation_upgrades_df)
model.define(SubstationUpgrade.new(
    id=src.ID, substation=Substation.lookup(id=src.SUBSTATION_ID),
    capacity_increase_mw=src.CAPACITY_INCREASE_MW, cost_million=src.COST_MILLION,
    lead_time_months=src.LEAD_TIME_MONTHS, enables_low_carbon=src.ENABLES_LOW_CARBON,
))

# Load demand forecast data from CSV.
src = model.data(demand_forecasts_df)
model.define(DemandForecast.new(
    id=src.ID, substation=Substation.lookup(id=src.SUBSTATION_ID),
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
    substation=Substation.lookup(id=src.SUBSTATION_ID),
))

# Load DC announcement data from CSV.
src = model.data(dc_announcements_df)
model.define(DCAnnouncement.new(
    id=src.ANNOUNCEMENT_ID, hyperscaler=src.HYPERSCALER,
    announced_date=src.ANNOUNCED_DATE, announced_mw=src.ANNOUNCED_MW,
    substation=Substation.lookup(id=src.SUBSTATION_ID),
))

# Investment levels: the budget scenarios the one solve is indexed by.
inv_data = model.data(pd.DataFrame([
    {"name": "$200M", "budget_cap": 200.0},
    {"name": "$300M", "budget_cap": 300.0},
    {"name": "$400M", "budget_cap": 400.0},
    {"name": "$500M", "budget_cap": 500.0},
    {"name": "$600M", "budget_cap": 600.0},
]))
model.define(InvestmentLevel.new(inv_data.to_schema()))
