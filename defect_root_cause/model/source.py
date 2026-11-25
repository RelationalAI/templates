"""Load the sample genealogy corpus: SKUs, lots, units, process history, and candidate factors."""

from pathlib import Path

from pandas import read_csv

from .schema import SKU, BillOfMaterials, Factor, Lot, Machine, Supplier, Unit, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --- Load the corpus (explicit binding; CSV columns are upper-case) ---

# SKUs and bill of materials.
sd = model.data(read_csv(DATA_DIR / "skus.csv"))
model.define(sku := SKU.new(id=sd.SKU_ID), sku.name(sd.NAME), sku.tier(sd.TIER))
bd = model.data(read_csv(DATA_DIR / "bill_of_materials.csv"))
model.define(
    b := BillOfMaterials.new(id=bd.BOM_ID),
    b.output_sku(SKU.lookup(id=bd.OUTPUT_SKU_ID)),
    b.input_sku(SKU.lookup(id=bd.INPUT_SKU_ID)),
)

# Suppliers and machines.
spd = model.data(read_csv(DATA_DIR / "suppliers.csv"))
model.define(s := Supplier.new(id=spd.SUPPLIER_ID), s.name(spd.NAME))
md = model.data(read_csv(DATA_DIR / "machines.csv"))
model.define(
    m := Machine.new(id=md.MACHINE_ID),
    m.name(md.NAME),
    m.machine_type(md.MACHINE_TYPE),
    m.calibration_age_days(md.CALIBRATION_AGE_DAYS),
)

# Lots and the genealogy edges between them.
ld = model.data(read_csv(DATA_DIR / "lots.csv"))
model.define(
    lot := Lot.new(id=ld.LOT_ID),
    lot.sku(SKU.lookup(id=ld.SKU_ID)),
    lot.supplier(Supplier.lookup(id=ld.SUPPLIER_ID)),
    lot.received_date(ld.RECEIVED_DATE),
)
gd = model.data(read_csv(DATA_DIR / "lot_genealogy.csv"))
model.define(Lot.lookup(id=gd.PARENT_LOT_ID).consumes(Lot.lookup(id=gd.CHILD_LOT_ID)))

# Units, their final-test result, and the top-tier lots they consume.
ud = model.data(read_csv(DATA_DIR / "units.csv"))
model.define(
    u := Unit.new(id=ud.UNIT_ID),
    u.sku(SKU.lookup(id=ud.SKU_ID)),
    u.build_date(ud.BUILD_DATE),
    u.defective(ud.DEFECTIVE),
    u.defect_type(ud.DEFECT_TYPE),
    u.shift(ud.SHIFT),
    u.build_week(ud.BUILD_WEEK),
)
model.define(Unit.is_defective(u := Unit.ref())).where(u.defective == 1)
uld = model.data(read_csv(DATA_DIR / "unit_lots.csv"))
model.define(Unit.lookup(id=uld.UNIT_ID).consumes_lot(Lot.lookup(id=uld.LOT_ID)))

# Process history: which machine ran each operation on each unit.
ppd = model.data(read_csv(DATA_DIR / "unit_process.csv"))
model.define(Unit.lookup(id=ppd.UNIT_ID).ran_on(Machine.lookup(id=ppd.MACHINE_ID)))

# Candidate factors. REF_ID names the factor's lot, machine, or shift, so each
# kind's rule binds the matching back-pointer.
fd = model.data(read_csv(DATA_DIR / "factors.csv"))
model.define(f := Factor.new(id=fd.FACTOR_ID), f.kind(fd.KIND), f.label(fd.LABEL))
model.where(fd.KIND == "LOT").define(
    Factor.lookup(id=fd.FACTOR_ID).lot(Lot.lookup(id=fd.REF_ID))
)
model.where(fd.KIND == "MACHINE").define(
    Factor.lookup(id=fd.FACTOR_ID).machine(Machine.lookup(id=fd.REF_ID))
)
model.where(fd.KIND == "SHIFT").define(Factor.lookup(id=fd.FACTOR_ID).shift_name(fd.REF_ID))
