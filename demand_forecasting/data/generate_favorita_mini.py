"""Generate synthetic Favorita-shaped retail data for the demand_forecasting
template.

Produces three CSVs under data/favorita_mini/:
  - stores.csv     (3 stores × 4 attrs)
  - items.csv      (25 items × 5 attrs across 5 families)
  - sales.csv      (3 × 25 × 365 = ~27K daily rows with unit_sales,
                    onpromotion flag, day-of-week and month seasonality,
                    promotion-day spikes, and noise)

Run once to regenerate:
    python data/generate_favorita_mini.py

The output is committed under data/favorita_mini/. The actual template
script (demand_forecasting.py) reads those CSVs.
"""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

OUT_DIR = Path(__file__).parent / "favorita_mini"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEED = 42
rng = np.random.default_rng(SEED)

# --------------------------------------------------
# Stores
# --------------------------------------------------

stores = pd.DataFrame(
    [
        {"store_id": 1, "city": "Quito", "state": "Pichincha", "store_type": "A", "cluster": 13},
        {"store_id": 2, "city": "Guayaquil", "state": "Guayas", "store_type": "B", "cluster": 8},
        {"store_id": 3, "city": "Cuenca", "state": "Azuay", "store_type": "C", "cluster": 4},
    ]
)
stores.to_csv(OUT_DIR / "stores.csv", index=False)

# Per-store base demand multiplier — Quito (city A) higher volume than Cuenca (C)
store_factor = {1: 1.4, 2: 1.0, 3: 0.6}

# --------------------------------------------------
# Items
# --------------------------------------------------

families = ["BEVERAGES", "DAIRY", "GROCERY", "BAKERY", "CLEANING"]
item_rows = []
item_id = 1
for fam in families:
    for _ in range(5):
        item_rows.append(
            {
                "item_id": item_id,
                "family": fam,
                "item_class": int(rng.integers(1000, 9999)),
                "perishable": fam in ("DAIRY", "BAKERY"),
            }
        )
        item_id += 1
items = pd.DataFrame(item_rows)
items.to_csv(OUT_DIR / "items.csv", index=False)

# Per-family base demand multiplier
family_factor = {
    "BEVERAGES": 1.3,
    "DAIRY": 1.1,
    "GROCERY": 1.2,
    "BAKERY": 0.9,
    "CLEANING": 0.7,
}

# Per-item base demand around the family base
item_base = {
    int(r.item_id): family_factor[r.family] * float(rng.uniform(8, 22))
    for r in items.itertuples()
}

# --------------------------------------------------
# Sales (daily, per store × item)
# --------------------------------------------------

start = date(2024, 1, 1)
n_days = 365
dates = [start + timedelta(days=i) for i in range(n_days)]

sale_rows = []
sale_id = 1
for d in dates:
    # Weekly seasonality: weekend boost
    weekday = d.weekday()  # 0=Mon
    weekend_factor = 1.25 if weekday >= 5 else 1.0
    # Monthly seasonality: end-of-year holiday spike
    if d.month == 12:
        seasonal_factor = 1.4
    elif d.month in (6, 7):
        seasonal_factor = 1.1  # mild summer bump
    else:
        seasonal_factor = 1.0
    for store_id in (1, 2, 3):
        for it in items.itertuples():
            # Random ~5% chance of promotion on any (store, item, day)
            on_promotion = rng.random() < 0.05
            promo_factor = 1.6 if on_promotion else 1.0
            base = item_base[int(it.item_id)] * store_factor[store_id]
            mean = base * weekend_factor * seasonal_factor * promo_factor
            # Negative-binomial-ish noise (Poisson with overdispersion)
            unit_sales = max(0, int(rng.poisson(mean) + rng.integers(-2, 3)))
            sale_rows.append(
                {
                    "sale_id": sale_id,
                    "date": d.isoformat(),
                    "store_id": store_id,
                    "item_id": int(it.item_id),
                    "unit_sales": unit_sales,
                    "onpromotion": on_promotion,
                }
            )
            sale_id += 1

sales = pd.DataFrame(sale_rows)
sales.to_csv(OUT_DIR / "sales.csv", index=False)

print(f"Generated {len(stores)} stores, {len(items)} items, {len(sales):,} sales rows")
print(f"Sales date range: {sales['date'].min()} to {sales['date'].max()}")
print(f"Mean unit_sales: {sales['unit_sales'].mean():.2f}, max: {sales['unit_sales'].max()}")
print(f"Promotion rate: {sales['onpromotion'].mean():.1%}")
