"""Generate the synthetic electronics-assembly traceability corpus for the
defect_root_cause template.

The corpus is a serialized-unit manufacturing genealogy for a consumer
electronics line (smartphones + tablet) built from a multi-tier bill of
materials. Each finished unit carries its full material genealogy (which
lots, transitively, went into it) and its process history (which machine
and shift ran each operation). A subset of units fail final test.

Two root causes are planted so the downstream RCA chain has a defensible,
non-obvious answer, and several decoys are planted so contrast scoring and
the diagnosis MILP have to earn their result:

  Root cause 1 -- solder-paste lot SP-0423 (supplier Meridian Components)
    is contaminated. It is consumed, through the SA-PCBA sub-assembly, by
    ~15% of units, which then fail final test with COLD_SOLDER defects far
    above baseline. SP-0423 sits two genealogy hops below the finished
    unit, so only transitive backward reachability surfaces it.

  Root cause 2 -- reflow oven REF-02 drifts out of calibration partway
    through the window. Units reflowed on REF-02 after the drift date fail
    with SOLDER_BRIDGE defects. Paste-exposed units are routed away from
    REF-02, so the two causes hit largely disjoint unit sets -- the
    minimal explanation needs both (a size-2 diagnosis).

  Decoys -- a near-universal housing lot (CP-HOUS-L01, reaches ~all units
    at baseline defect rate), a high-volume placement machine (SMT-01,
    ~70% of volume), and the day shift (~45% of volume). Each "covers"
    many defects but also many good units, so high coverage with low lift
    must not be mistaken for a cause.

Run:
    python generate_data.py

Output:
    Writes nine CSVs to ./data/ and prints a verification report
    (overall defect rate, per-factor defect rate and lift, and the
    expected minimal diagnosis) so the planted narrative is auditable.
"""

import random
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

SEED = 42
random.seed(SEED)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# --------------------------------------------------
# Calendar
# --------------------------------------------------

WINDOW_START = date(2026, 2, 2)
WINDOW_DAYS = 21
DRIFT_DAY = 6  # REF-02 calibration drift begins WINDOW_START + DRIFT_DAY


def day(offset: int) -> date:
    return WINDOW_START + timedelta(days=offset)


def rand_day() -> date:
    return day(random.randint(0, WINDOW_DAYS - 1))


# --------------------------------------------------
# SKUs + bill of materials (consumer electronics, four tiers)
# --------------------------------------------------

SKUS = [
    ("FG-PHN-A", "Aurora Smartphone", "FINISHED"),
    ("FG-PHN-B", "Borealis Smartphone", "FINISHED"),
    ("FG-TAB-C", "Cirrus Tablet", "FINISHED"),
    ("SA-PCBA", "Main PCBA (populated board)", "SUBASSEMBLY"),
    ("SA-BATT", "Battery Pack", "SUBASSEMBLY"),
    ("SA-DISP", "Display Module", "SUBASSEMBLY"),
    ("SA-ENC", "Enclosure Assembly", "SUBASSEMBLY"),
    ("CP-PCB", "Bare PCB", "COMPONENT"),
    ("CP-PASTE", "Solder Paste", "COMPONENT"),
    ("CP-SOC", "Application SoC", "COMPONENT"),
    ("CP-MEM", "Memory IC", "COMPONENT"),
    ("CP-PASS", "Passives Kit", "COMPONENT"),
    ("CP-CELL", "Battery Cell", "COMPONENT"),
    ("CP-LCD", "LCD Panel", "COMPONENT"),
    ("CP-HOUS", "Housing Shell", "COMPONENT"),
    ("RM-CU", "Copper Foil", "RAW"),
    ("RM-RESIN", "Laminate Resin", "RAW"),
    ("RM-LI", "Lithium Compound", "RAW"),
    ("RM-SI", "Silicon Wafer", "RAW"),
    ("RM-POLY", "Polymer Pellets", "RAW"),
]

FINISHED = [s[0] for s in SKUS if s[2] == "FINISHED"]

# output SKU requires input SKU
BOM = [
    ("FG-PHN-A", "SA-PCBA"), ("FG-PHN-A", "SA-BATT"), ("FG-PHN-A", "SA-DISP"), ("FG-PHN-A", "SA-ENC"),
    ("FG-PHN-B", "SA-PCBA"), ("FG-PHN-B", "SA-BATT"), ("FG-PHN-B", "SA-DISP"), ("FG-PHN-B", "SA-ENC"),
    ("FG-TAB-C", "SA-PCBA"), ("FG-TAB-C", "SA-BATT"), ("FG-TAB-C", "SA-DISP"), ("FG-TAB-C", "SA-ENC"),
    ("SA-PCBA", "CP-PCB"), ("SA-PCBA", "CP-PASTE"), ("SA-PCBA", "CP-SOC"), ("SA-PCBA", "CP-MEM"), ("SA-PCBA", "CP-PASS"),
    ("SA-BATT", "CP-CELL"),
    ("SA-DISP", "CP-LCD"),
    ("SA-ENC", "CP-HOUS"),
    ("CP-PCB", "RM-CU"), ("CP-PCB", "RM-RESIN"),
    ("CP-CELL", "RM-LI"),
    ("CP-SOC", "RM-SI"), ("CP-MEM", "RM-SI"),
    ("CP-HOUS", "RM-POLY"),
]

# --------------------------------------------------
# Suppliers + machines
# --------------------------------------------------

SUPPLIERS = [
    ("SUP-MERIDIAN", "Meridian Components"),
    ("SUP-NORTHGATE", "Northgate Materials"),
    ("SUP-PACIFICA", "Pacifica Semiconductor"),
    ("SUP-VANTAGE", "Vantage Cells"),
    ("SUP-CLARITY", "Clarity Displays"),
    ("SUP-IRONWOOD", "Ironwood Plastics"),
    ("SUP-APEX", "Apex Laminates"),
    ("SUP-INTERNAL", "In-house Assembly"),
]

# which supplier sources each purchased SKU (sub-assemblies are in-house)
SKU_SUPPLIER = {
    "SA-PCBA": "SUP-INTERNAL", "SA-BATT": "SUP-INTERNAL",
    "SA-DISP": "SUP-INTERNAL", "SA-ENC": "SUP-INTERNAL",
    "CP-PCB": "SUP-APEX", "CP-PASTE": "SUP-MERIDIAN", "CP-SOC": "SUP-PACIFICA",
    "CP-MEM": "SUP-PACIFICA", "CP-PASS": "SUP-NORTHGATE", "CP-CELL": "SUP-VANTAGE",
    "CP-LCD": "SUP-CLARITY", "CP-HOUS": "SUP-IRONWOOD",
    "RM-CU": "SUP-NORTHGATE", "RM-RESIN": "SUP-APEX", "RM-LI": "SUP-VANTAGE",
    "RM-SI": "SUP-PACIFICA", "RM-POLY": "SUP-IRONWOOD",
}

# MACHINE_ID, NAME, TYPE, calibration age in days (REF-02 is overdue)
MACHINES = [
    ("SMT-01", "Pick-and-place line 1", "SMT_PLACEMENT", 20),
    ("SMT-02", "Pick-and-place line 2", "SMT_PLACEMENT", 25),
    ("SMT-03", "Pick-and-place line 3", "SMT_PLACEMENT", 18),
    ("REF-01", "Reflow oven 1", "REFLOW", 22),
    ("REF-02", "Reflow oven 2", "REFLOW", 168),
    ("REF-03", "Reflow oven 3", "REFLOW", 30),
    ("ASM-01", "Final assembly cell 1", "FINAL_ASSEMBLY", 40),
    ("ASM-02", "Final assembly cell 2", "FINAL_ASSEMBLY", 35),
    ("TST-01", "Functional test rig 1", "FUNCTIONAL_TEST", 15),
    ("TST-02", "Functional test rig 2", "FUNCTIONAL_TEST", 19),
]

SMT = ["SMT-01", "SMT-02", "SMT-03"]
REFLOW = ["REF-01", "REF-02", "REF-03"]
ASM = ["ASM-01", "ASM-02"]
TST = ["TST-01", "TST-02"]
SHIFTS = ["DAY", "SWING", "NIGHT"]

# --------------------------------------------------
# Lots -- how many per purchased / built SKU
# --------------------------------------------------

LOT_COUNTS = {
    "SA-PCBA": 20, "SA-BATT": 10, "SA-DISP": 10, "SA-ENC": 8,
    "CP-PCB": 8, "CP-PASTE": 6, "CP-SOC": 5, "CP-MEM": 5, "CP-PASS": 4,
    "CP-CELL": 6, "CP-LCD": 6, "CP-HOUS": 2,
    "RM-CU": 3, "RM-RESIN": 3, "RM-LI": 3, "RM-SI": 4, "RM-POLY": 2,
}

BAD_PASTE_LOT = "SP-0423"  # root cause 1

lots = []           # (LOT_ID, SKU_ID, SUPPLIER_ID, RECEIVED_DATE)
lots_by_sku = defaultdict(list)


def lot_id(sku: str, i: int) -> str:
    # Solder-paste lots use the receiving-log convention SP-04xx so the
    # contaminated lot reads naturally in the narrative; others are <SKU>-Lnn.
    if sku == "CP-PASTE":
        return f"SP-04{19 + i:02d}"
    return f"{sku}-L{i + 1:02d}"


for sku, n in LOT_COUNTS.items():
    for i in range(n):
        lid = lot_id(sku, i)
        lots.append((lid, sku, SKU_SUPPLIER[sku], rand_day().isoformat()))
        lots_by_sku[sku].append(lid)

# --------------------------------------------------
# Lot genealogy -- which child lots each built lot consumed
# --------------------------------------------------

genealogy = []  # (PARENT_LOT_ID, CHILD_LOT_ID)


def pick_lot(sku: str) -> str:
    return random.choice(lots_by_sku[sku])


# SA-PCBA lots: ~15% of finished volume should be paste-exposed. With 20
# PCBA lots used roughly uniformly, tag 3 of them as built with SP-0423.
pcba_lots = lots_by_sku["SA-PCBA"]
paste_exposed_pcba = set(random.sample(pcba_lots, 3))
for pcba in pcba_lots:
    paste = BAD_PASTE_LOT if pcba in paste_exposed_pcba else random.choice(
        [lid for lid in lots_by_sku["CP-PASTE"] if lid != BAD_PASTE_LOT]
    )
    genealogy.append((pcba, paste))
    for child_sku in ("CP-PCB", "CP-SOC", "CP-MEM", "CP-PASS"):
        genealogy.append((pcba, pick_lot(child_sku)))

for batt in lots_by_sku["SA-BATT"]:
    genealogy.append((batt, pick_lot("CP-CELL")))
for disp in lots_by_sku["SA-DISP"]:
    genealogy.append((disp, pick_lot("CP-LCD")))
# Housing: 7 of 8 enclosure lots draw the same dominant housing lot
# (CP-HOUS-L01) -> a near-universal "trunk" lot decoy.
hous_dominant = lots_by_sku["CP-HOUS"][0]
for j, enc in enumerate(lots_by_sku["SA-ENC"]):
    genealogy.append((enc, hous_dominant if j > 0 else lots_by_sku["CP-HOUS"][1]))
for pcb in lots_by_sku["CP-PCB"]:
    genealogy.append((pcb, pick_lot("RM-CU")))
    genealogy.append((pcb, pick_lot("RM-RESIN")))
for cell in lots_by_sku["CP-CELL"]:
    genealogy.append((cell, pick_lot("RM-LI")))
for soc in lots_by_sku["CP-SOC"]:
    genealogy.append((soc, pick_lot("RM-SI")))
for mem in lots_by_sku["CP-MEM"]:
    genealogy.append((mem, pick_lot("RM-SI")))
for hous in lots_by_sku["CP-HOUS"]:
    genealogy.append((hous, pick_lot("RM-POLY")))

# child lookup for transitive ancestor (upstream-input) closure
children = defaultdict(list)
for parent, child in genealogy:
    children[parent].append(child)


def ancestor_lots(top_lots: list[str]) -> set[str]:
    """All lots transitively consumed, following parent -> child edges."""
    seen, q = set(), deque(top_lots)
    while q:
        lot = q.popleft()
        if lot in seen:
            continue
        seen.add(lot)
        q.extend(children.get(lot, ()))
    return seen


# --------------------------------------------------
# Units -- finished serial numbers, genealogy, process, test result
# --------------------------------------------------

N_UNITS = 2500
BASE_P = 0.012
RC1_ADD = 0.18   # paste-exposed -> COLD_SOLDER
RC2_ADD = 0.16   # REF-02 after drift -> SOLDER_BRIDGE
BASELINE_DEFECTS = ["MISSING_COMPONENT", "TOMBSTONE", "MISALIGNMENT", "COLD_SOLDER", "SOLDER_BRIDGE"]

units = []          # (UNIT_ID, SKU_ID, BUILD_DATE, DEFECTIVE, DEFECT_TYPE)
unit_lots = []      # (UNIT_ID, LOT_ID)  -- top-tier lots consumed directly
unit_process = []   # (UNIT_ID, OPERATION, MACHINE_ID, SHIFT, RUN_TS)

for u in range(N_UNITS):
    uid = f"U-{u + 1:05d}"
    sku = random.choices(FINISHED, weights=[0.4, 0.35, 0.25])[0]
    bdate = rand_day()

    # top-tier lots consumed by the finished unit
    top = [pick_lot("SA-PCBA"), pick_lot("SA-BATT"), pick_lot("SA-DISP"), pick_lot("SA-ENC")]
    for lid in top:
        unit_lots.append((uid, lid))
    anc = ancestor_lots(top)
    paste_exposed = BAD_PASTE_LOT in anc

    # process routing. Paste-exposed boards are routed away from REF-02 so
    # the two root causes hit largely disjoint unit sets.
    if paste_exposed:
        reflow = random.choices(REFLOW, weights=[0.45, 0.10, 0.45])[0]
    else:
        reflow = random.choices(REFLOW, weights=[0.40, 0.25, 0.35])[0]
    smt = random.choices(SMT, weights=[0.70, 0.18, 0.12])[0]
    shift = random.choices(SHIFTS, weights=[0.45, 0.35, 0.20])[0]
    bts = datetime.combine(bdate, datetime.min.time()).isoformat()
    unit_process.append((uid, "SMT_PLACEMENT", smt, shift, bts))
    unit_process.append((uid, "REFLOW", reflow, shift, bts))
    unit_process.append((uid, "FINAL_ASSEMBLY", random.choice(ASM), shift, bts))
    unit_process.append((uid, "FUNCTIONAL_TEST", random.choice(TST), shift, bts))

    rc2_active = (reflow == "REF-02") and ((bdate - WINDOW_START).days >= DRIFT_DAY)

    # test outcome: independent failure mechanisms compose
    defect_type = ""
    if random.random() < BASE_P:
        defect_type = random.choice(BASELINE_DEFECTS)
    if paste_exposed and random.random() < RC1_ADD:
        defect_type = "COLD_SOLDER"
    if rc2_active and random.random() < RC2_ADD:
        defect_type = "SOLDER_BRIDGE"
    defective = 1 if defect_type else 0
    units.append((uid, sku, bdate.isoformat(), defective, defect_type or "NONE", shift))

# --------------------------------------------------
# Write CSVs
# --------------------------------------------------

pd.DataFrame(SKUS, columns=["SKU_ID", "NAME", "TIER"]).to_csv(DATA_DIR / "skus.csv", index=False)
pd.DataFrame(
    [(f"BOM-{i + 1:03d}", o, inp) for i, (o, inp) in enumerate(BOM)],
    columns=["BOM_ID", "OUTPUT_SKU_ID", "INPUT_SKU_ID"],
).to_csv(DATA_DIR / "bill_of_materials.csv", index=False)
pd.DataFrame(SUPPLIERS, columns=["SUPPLIER_ID", "NAME"]).to_csv(DATA_DIR / "suppliers.csv", index=False)
pd.DataFrame(
    [(mid, name, mtype, (WINDOW_START - timedelta(days=age)).isoformat(), age) for mid, name, mtype, age in MACHINES],
    columns=["MACHINE_ID", "NAME", "MACHINE_TYPE", "LAST_CALIBRATION_DATE", "CALIBRATION_AGE_DAYS"],
).to_csv(DATA_DIR / "machines.csv", index=False)
pd.DataFrame(lots, columns=["LOT_ID", "SKU_ID", "SUPPLIER_ID", "RECEIVED_DATE"]).to_csv(DATA_DIR / "lots.csv", index=False)
pd.DataFrame(genealogy, columns=["PARENT_LOT_ID", "CHILD_LOT_ID"]).to_csv(DATA_DIR / "lot_genealogy.csv", index=False)
pd.DataFrame(units, columns=["UNIT_ID", "SKU_ID", "BUILD_DATE", "DEFECTIVE", "DEFECT_TYPE", "SHIFT"]).to_csv(DATA_DIR / "units.csv", index=False)
pd.DataFrame(unit_lots, columns=["UNIT_ID", "LOT_ID"]).to_csv(DATA_DIR / "unit_lots.csv", index=False)
pd.DataFrame(unit_process, columns=["UNIT_ID", "OPERATION", "MACHINE_ID", "SHIFT", "RUN_TS"]).to_csv(DATA_DIR / "unit_process.csv", index=False)

# Candidate factors -- the universe the diagnosis ranges over. Any lot
# (reached transitively through genealogy), any machine, or any shift is a
# possible cause; the rules stage scores them and the MILP picks a minimal
# explanatory set. REF_ID points back to the underlying Lot / Machine id or
# shift name so the incidence relationship can be derived in-engine.
factors = []
for lid, sku, _sup, _rd in lots:
    factors.append((f"LOT::{lid}", "LOT", f"{sku} lot {lid}", lid))
for mid, name, mtype, _age in MACHINES:
    factors.append((f"MACHINE::{mid}", "MACHINE", f"{name} ({mtype})", mid))
for sh in SHIFTS:
    factors.append((f"SHIFT::{sh}", "SHIFT", f"{sh} shift", sh))
pd.DataFrame(factors, columns=["FACTOR_ID", "KIND", "LABEL", "REF_ID"]).to_csv(DATA_DIR / "factors.csv", index=False)
print(f"Candidate factors: {len(factors)} ({sum(k == 'LOT' for _, k, _, _ in factors)} lots, "
      f"{len(MACHINES)} machines, {len(SHIFTS)} shifts)")

# --------------------------------------------------
# Verification report -- the planted narrative must be auditable
# --------------------------------------------------

udf = pd.DataFrame(units, columns=["UNIT_ID", "SKU_ID", "BUILD_DATE", "DEFECTIVE", "DEFECT_TYPE", "SHIFT"])
n = len(udf)
n_def = int(udf["DEFECTIVE"].sum())
base_rate = n_def / n

# per-unit factor membership (lots via transitive genealogy; machines/shift via process)
unit_anc = {uid: ancestor_lots([lid for (x, lid) in unit_lots if x == uid]) for uid in udf["UNIT_ID"]}
proc_by_unit = defaultdict(dict)
for uid, op, mid, sh, _ in unit_process:
    proc_by_unit[uid][op] = mid
    proc_by_unit[uid]["SHIFT"] = sh

defective = dict(zip(udf["UNIT_ID"], udf["DEFECTIVE"]))


def factor_stats(member_fn, label):
    members = [uid for uid in udf["UNIT_ID"] if member_fn(uid)]
    d = sum(defective[uid] for uid in members)
    rate = d / len(members) if members else 0.0
    lift = (rate / base_rate) if base_rate else 0.0
    return label, len(members), d, rate, lift


print("=" * 72)
print("DEFECT ROOT CAUSE -- DATA VERIFICATION")
print("=" * 72)
print(f"Units: {n}   Defective: {n_def}   Overall final-test failure rate: {base_rate:.2%}")
print(f"Defect-type mix:\n{udf[udf.DEFECTIVE == 1]['DEFECT_TYPE'].value_counts().to_string()}")

rows = [
    factor_stats(lambda uid: BAD_PASTE_LOT in unit_anc[uid], f"LOT {BAD_PASTE_LOT} (paste, RC1)"),
    factor_stats(lambda uid: proc_by_unit[uid].get("REFLOW") == "REF-02", "MACHINE REF-02 (reflow, RC2)"),
    factor_stats(lambda uid: hous_dominant in unit_anc[uid], f"LOT {hous_dominant} (housing, DECOY-trunk)"),
    factor_stats(lambda uid: proc_by_unit[uid].get("SMT_PLACEMENT") == "SMT-01", "MACHINE SMT-01 (DECOY-popular)"),
    factor_stats(lambda uid: proc_by_unit[uid].get("SHIFT") == "DAY", "SHIFT DAY (DECOY)"),
]
print(f"\n{'factor':<40}{'units':>7}{'defects':>9}{'rate':>9}{'lift':>8}")
for label, m, d, rate, lift in rows:
    print(f"{label:<40}{m:>7}{d:>9}{rate:>8.1%}{lift:>7.1f}x")

# overlap of the two true causes
both = [uid for uid in udf["UNIT_ID"]
        if BAD_PASTE_LOT in unit_anc[uid] and proc_by_unit[uid].get("REFLOW") == "REF-02"]
rc1_def = [uid for uid in udf["UNIT_ID"] if BAD_PASTE_LOT in unit_anc[uid] and defective[uid]]
rc2_def = [uid for uid in udf["UNIT_ID"]
           if proc_by_unit[uid].get("REFLOW") == "REF-02" and defective[uid]]
covered = len(set(rc1_def) | set(rc2_def))
print(f"\nRC1 ∩ RC2 unit overlap: {len(both)} units (kept small -> 2-factor diagnosis)")
print(f"Defects explained by {{SP-0423, REF-02}}: {covered}/{n_def} ({covered / n_def:.0%})")
print("Expected minimal diagnosis: {LOT SP-0423, MACHINE REF-02}")
print("=" * 72)
