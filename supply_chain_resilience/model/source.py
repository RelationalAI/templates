"""Load the sample sites, businesses, SKUs, operations, demand, shipments, and delay predictions into the supply chain model."""

from pathlib import Path

from pandas import read_csv

from .schema import (
    SKU,
    Business,
    DelayPrediction,
    Demand,
    Operation,
    Shipment,
    Site,
    model,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

site_data = model.data(read_csv(DATA_DIR / "site.csv"))
model.define(
    s := Site.new(id=site_data["ID"]),
    s.name(site_data["NAME"]),
    s.site_type(site_data["SITE_TYPE"]),
    s.region(site_data["REGION"]),
    s.country(site_data["COUNTRY"]),
)

biz_csv = read_csv(DATA_DIR / "business.csv")

# Load businesses in two batches: with and without reliability score.
# Only pass needed columns to model.data() — extra columns with NaN
# values cause data loading issues.
biz_cols = ["ID", "NAME", "TYPE", "SITE_ID", "RELIABILITY_SCORE"]
biz_with_rel = biz_csv.dropna(subset=["RELIABILITY_SCORE"])[biz_cols].reset_index(drop=True)
biz_no_rel = biz_csv[biz_csv["RELIABILITY_SCORE"].isna()][biz_cols[:4]].reset_index(drop=True)

# Batch 1: businesses WITH reliability (suppliers, manufacturers).
d1 = model.data(biz_with_rel)
model.define(
    b1 := Business.new(id=d1["ID"], site=Site.lookup(id=d1["SITE_ID"])),
    b1.name(d1["NAME"]),
    b1.business_type(d1["TYPE"]),
    b1.reliability_score(d1["RELIABILITY_SCORE"]),
)

# Batch 2: businesses WITHOUT reliability (buyers, warehouses).
if len(biz_no_rel) > 0:
    d2 = model.data(biz_no_rel)
    model.define(
        b2 := Business.new(id=d2["ID"], site=Site.lookup(id=d2["SITE_ID"])),
        b2.name(d2["NAME"]),
        b2.business_type(d2["TYPE"]),
    )

sku_data = model.data(read_csv(DATA_DIR / "sku.csv"))
model.define(
    sk := SKU.new(id=sku_data["ID"]),
    sk.name(sku_data["NAME"]),
    sk.sku_type(sku_data["TYPE"]),
)

op_data = model.data(read_csv(DATA_DIR / "operation.csv"))
model.define(
    o := Operation.new(id=op_data["ID"]),
    o.op_type(op_data["TYPE"]),
    o.transit_time_days(op_data["TRANSIT_TIME_DAYS"]),
    o.cost_per_unit(op_data["COST_PER_UNIT"]),
    o.capacity_per_day(op_data["CAPACITY_PER_DAY"]),
    o.source_site(Site.lookup(id=op_data["SOURCE_SITE_ID"])),
    o.output_site(Site.lookup(id=op_data["OUTPUT_SITE_ID"])),
    o.output_sku(SKU.lookup(id=op_data["OUTPUT_SKU"])),
)

dem_data = model.data(read_csv(DATA_DIR / "demand.csv"))
model.define(
    d := Demand.new(id=dem_data["ID"]),
    d.quantity(dem_data["QUANTITY"]),
    d.priority(dem_data["PRIORITY"]),
    d.business(Business.lookup(id=dem_data["BUSINESS_ID"])),
    d.sku(SKU.lookup(id=dem_data["SKU_ID"])),
)

# Shipment data: only the columns the graph and the late-shipment statistics need.
shipments_csv = read_csv(DATA_DIR / "shipment.csv")
ship_cols = ["ID", "SUPPLIER_BUSINESS_ID", "CUSTOMER_BUSINESS_ID", "SKU_ID", "QUANTITY"]
ship_data = model.data(shipments_csv[ship_cols])
model.define(
    sh := Shipment.new(id=ship_data["ID"]),
    sh.supplier(Business.lookup(id=ship_data["SUPPLIER_BUSINESS_ID"])),
    sh.customer(Business.lookup(id=ship_data["CUSTOMER_BUSINESS_ID"])),
    sh.sku_id(ship_data["SKU_ID"]),
    sh.quantity(ship_data["QUANTITY"]),
)

# A shipment's delay is recorded once it has arrived; a shipment still in transit has none.
delay_data = model.data(shipments_csv.dropna(subset=["DELAY_DAYS"])[["ID", "DELAY_DAYS"]])
model.define(
    sh_delay := Shipment.new(id=delay_data["ID"]),
    sh_delay.delay_days(delay_data["DELAY_DAYS"]),
)

pred_data = model.data(read_csv(DATA_DIR / "delay_prediction.csv"))
model.define(
    dp := DelayPrediction.new(id=pred_data["ID"]),
    dp.fiscal_quarter(pred_data["FISCAL_QUARTER"]),
    dp.predicted_delay_prob(pred_data["PREDICTED_DELAY_PROB"]),
    dp.risk_tier(pred_data["RISK_TIER"]),
    dp.supplier_business(Business.lookup(id=pred_data["SUPPLIER_BUSINESS_ID"])),
)
