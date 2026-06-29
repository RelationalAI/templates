"""Generate a learnable GNN training corpus for the supply_chain_resilience template.

The bundled shipment.csv (~262 rows) is far too sparse to train a GNN, so this builds
an independent, multi-year labelled corpus from the template's OWN businesses, supply
graph, and reliability scores. Delay risk combines four signals a GNN must learn jointly:
each supplier's stationary reliability, one-hop upstream propagation through the supply
graph (a reliable shipper fed by an unreliable upstream is itself risky), a recurring
year-end seasonal surge, and lead time. The signal is feature-driven (not a coin flip)
so it is strongly learnable, and graph-dependent so a GNN beats a per-supplier baseline.

Writes shipment_corpus.csv + shipment_{train,val,test}.csv (temporal split: train through
2024-Q3, validate on 2024-10, test on 2024-Q4) into the template's data/ dir. Independent
of the canonical shipment.csv, which is unchanged.

Run:  python data/generate_corpus.py
"""
import csv
import math
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).parent
SEED = 777
YEARS = [2022, 2023, 2024]
PER_YEAR = 2500  # ~7,500-row corpus

random.seed(SEED)

# ── read template data ───────────────────────────────────────────────────────
biz = {}
with open(DATA / "business.csv") as f:
    for r in csv.DictReader(f):
        rel = float(r["RELIABILITY_SCORE"]) if r.get("RELIABILITY_SCORE") else 0.90
        biz[r["ID"]] = {"type": r["TYPE"], "site": r["SITE_ID"], "rel": rel}
site_to_biz = {b["site"]: bid for bid, b in biz.items()}

ops = list(csv.DictReader(open(DATA / "operation.csv")))
op_transit = {o["ID"]: int(float(o["TRANSIT_TIME_DAYS"])) for o in ops if o.get("TRANSIT_TIME_DAYS")}

# Supply graph: a SHIP op SOURCE_SITE→OUTPUT_SITE means the business at OUTPUT is fed by
# the business at SOURCE. Build each business's one-hop upstream set.
upstream = {}
for o in ops:
    s, d = site_to_biz.get(o["SOURCE_SITE_ID"]), site_to_biz.get(o["OUTPUT_SITE_ID"])
    if s and d and s != d:
        upstream.setdefault(d, set()).add(s)

def _unrel(b):
    return 1.0 - biz[b]["rel"]

# Effective unreliability: own (amplified for a clear spread) + half the worst upstream.
# This is the graph signal — a high-own-reliability shipper inherits risk from its supplier.
eff_unrel = {}
for b in biz:
    worst_up = max((_unrel(u) for u in upstream.get(b, ())), default=0.0)
    eff_unrel[b] = min(0.85, 2.4 * _unrel(b) + 0.6 * worst_up)

# Distinct delivery lanes (supplier, customer, sku, origin, dest, op) from the bundled shipments.
lanes = {}
with open(DATA / "shipment.csv") as f:
    for r in csv.DictReader(f):
        key = (r["SUPPLIER_BUSINESS_ID"], r["CUSTOMER_BUSINESS_ID"], r["SKU_ID"],
               r["ORIGIN_SITE_ID"], r["DESTINATION_SITE_ID"], r["OPERATION_ID"])
        lanes[key] = op_transit.get(r["OPERATION_ID"], 4)
lane_list = list(lanes.items())

# ── generate labelled corpus ─────────────────────────────────────────────────
rows = []
sid = 1
for year in YEARS:
    for _ in range(PER_YEAR):
        (sup, cust, sku, origin, dest, op), transit = random.choice(lane_list)
        order = datetime(year, 1, 1) + timedelta(days=random.randint(0, 350))
        ship = order + timedelta(days=random.randint(1, 3))
        expected = ship + timedelta(days=transit)
        # feature-driven, mostly-deterministic delay risk (steep-but-capped sigmoid)
        risk = (eff_unrel[sup]
                + (0.08 if order.month in (10, 11, 12) else 0.0)   # recurring Q4 surge
                + 0.02 * (transit - 5))                            # lead time
        prob = 1.0 / (1.0 + math.exp(-7.5 * (risk - 0.42)))
        is_late = random.random() < min(0.90, max(0.02, prob))
        delay_days = random.randint(1, 10) if is_late else 0
        actual = expected + timedelta(days=delay_days if is_late else -random.randint(0, 1))
        rows.append({
            "ID": f"TSHP{sid:05d}",
            "SUPPLIER_BUSINESS_ID": sup, "CUSTOMER_BUSINESS_ID": cust, "SKU_ID": sku,
            "QUANTITY": random.randint(50, 300),
            "ORIGIN_SITE_ID": origin, "DESTINATION_SITE_ID": dest, "OPERATION_ID": op,
            "ORDER_DATE": order.strftime("%Y-%m-%d"), "SHIP_DATE": ship.strftime("%Y-%m-%d"),
            "EXPECTED_DELIVERY_DATE": expected.strftime("%Y-%m-%d"),
            "ACTUAL_DELIVERY_DATE": actual.strftime("%Y-%m-%d"),
            "STATUS": "DELAYED" if is_late else "DELIVERED",
            "DELAY_DAYS": delay_days,
            "SHIP_MONTH": ship.month, "SHIP_QUARTER": (ship.month - 1) // 3 + 1,
            "FISCAL_QUARTER": f"Q{(order.month - 1) // 3 + 1}-{year}", "FISCAL_YEAR": year,
            # the shipper's OWN reliability, denormalized as a node feature. It is
            # deliberately the raw score (not the propagated one), so the graph has
            # to correct it: B004 looks safe at 0.90 but its labels are risky.
            "SUPPLIER_RELIABILITY": round(biz[sup]["rel"], 3),
            "IS_LATE": int(is_late),
        })
        sid += 1
random.Random(SEED).shuffle(rows)

# ── Shipment relatedness edge list (homogeneous graph for a CSV-backed GNN) ───
# Each shipment links to a few others sharing its supplier (so per-supplier risk
# propagates) and to a few from its supplier's UPSTREAM suppliers (so an unreliable
# upstream's risky labels reach a high-own-reliability shipper like B004 <- B003).
by_sup = defaultdict(list)
for r in rows:
    by_sup[r["SUPPLIER_BUSINESS_ID"]].append(r["ID"])
erng = random.Random(SEED + 1)
edges, K_SAME, K_UP = [], 6, 4
for r in rows:
    sid_, sup = r["ID"], r["SUPPLIER_BUSINESS_ID"]
    peers = [p for p in by_sup.get(sup, []) if p != sid_]
    for _ in range(min(K_SAME, len(peers))):
        edges.append((sid_, erng.choice(peers)))
    # sorted(): upstream values are sets, whose iteration order is hash-randomized
    # per process — sort so the seeded erng.choice below yields reproducible edges.
    up_ships = [s for u in sorted(upstream.get(sup, ())) for s in by_sup.get(u, [])]
    for _ in range(min(K_UP, len(up_ships))):
        edges.append((sid_, erng.choice(up_ships)))
with open(DATA / "shipment_edges.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["SRC", "DST"])
    w.writerows(edges)

cols = list(rows[0].keys())
with open(DATA / "shipment_corpus.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

# temporal split by ship date
def ymd(r): return r["SHIP_DATE"]
label_cols = ["SHIPMENT_ID", "SHIP_DATE", "IS_LATE"]
def write_split(name, rs):
    with open(DATA / f"shipment_{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=label_cols)
        w.writeheader()
        for r in rs:
            w.writerow({"SHIPMENT_ID": r["ID"], "SHIP_DATE": r["SHIP_DATE"], "IS_LATE": r["IS_LATE"]})
ordered = sorted(rows, key=ymd)
train = [r for r in ordered if r["SHIP_DATE"] < "2024-10-01"]
val = [r for r in ordered if "2024-10-01" <= r["SHIP_DATE"] < "2024-11-01"]
test = [r for r in ordered if r["SHIP_DATE"] >= "2024-11-01"]
write_split("train", train)
write_split("val", val)
write_split("test", test)

n_late = sum(r["IS_LATE"] for r in rows)
print(f"corpus: {len(rows)} rows ({n_late} late, {n_late/len(rows):.1%}) | "
      f"train {len(train)} / val {len(val)} / test {len(test)} (temporal ≤2024-Q3 / 2024-10 / 2024-Q4)")
