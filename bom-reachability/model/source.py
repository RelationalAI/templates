"""Load the sample SKUs and bill of materials into the BOM model."""

from pathlib import Path

import pandas as pd
from relationalai.semantics import where

from .schema import SKU, BillOfMaterials, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

sku_data = model.data(pd.read_csv(DATA_DIR / "skus.csv"))
model.define(SKU.new(id=sku_data["ID"]))
where(SKU.id == sku_data["ID"]).define(
    SKU.name(sku_data["NAME"]),
    SKU.type(sku_data["TYPE"]),
    SKU.category(sku_data["CATEGORY"]),
)

bom_data = model.data(pd.read_csv(DATA_DIR / "bill_of_materials.csv"))
model.define(BillOfMaterials.new(id=bom_data["ID"]))
where(BillOfMaterials.id == bom_data["ID"]).define(
    BillOfMaterials.output_sku(SKU.lookup(id=bom_data["OUTPUT_SKU_ID"])),
    BillOfMaterials.input_sku(SKU.lookup(id=bom_data["INPUT_SKU_ID"])),
)
