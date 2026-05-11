"""Synthesize the augmented equipment-failure data for the telco template.

Generates four CSVs end-to-end with reproducible seed:

- network_equipment.csv     -- ~1,500 items across 250 towers, MODEL from
                               20-value catalog
- equipment_health.csv      -- 1:1 with equipment, rebalanced HEALTH_SCORE
- model_advisories.csv      -- 8 recall/defect/EOL/firmware/security
                               advisories on 7 of the 20 models, severity
                               0.50-0.95
- tower_upgrade_options.csv -- 250 towers x 3 tiers = 750 rows so every
                               tower is upgradeable

Reads cell_towers.csv (kept as-is) for tower IDs and regions.

Run from inside data/ with:
    python _synthesize_advisory_data.py

Design: AT_RISK is driven by FIVE signals that are deliberately hard to
reproduce with a SQL query. The GNN's heterogeneous topology -- with
edges across NetworkEquipment <-> CellTower <-> NetworkEquipment as
well as ModelAdvisory -> NetworkEquipment -- learns these patterns
naturally via message passing.

Latent risk model:

    latent_risk = 0.25 * advisory_severity_on_model
                + 0.45 * neighbor_advisory_severity     <-- 2-hop relational
                + 0.10 * health_gap
                + 0.05 * firmware_outdated_flag
                + 0.10 * three_way_interaction          <-- smooth product
                + 0.05 * noise

  AT_RISK = latent_risk > 0.50

Where:
  - neighbor_advisory_severity is the MAX advisory severity among OTHER
    equipment items on the same tower (the 2-hop GNN signal: your
    tower-mate's advisory boosts your own risk through the
    Equipment <-> Tower <-> Equipment path).
  - three_way_interaction = advisory_severity * health_gap *
    (firmware_outdated + 0.3) * 4 -- a smooth product term that fires
    only when ALL three of advisory / health / firmware signals are
    present at moderate levels. No single SQL threshold captures it.

A naive SQL filter on HEALTH_SCORE alone misses ~93% of true at-risk
equipment. Even a sophisticated join-aware SQL writer has to know
about the ModelAdvisory table, the tower-mate effect, AND the smooth
interaction -- three layers of ontology awareness the GNN learns from
training data automatically.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

SEED = 42
DATA_DIR = Path(__file__).parent

EQUIPMENT_COUNT_TARGET = 1500

# Per-equipment-type model catalog. Each tuple is (MODEL, MANUFACTURER,
# PART_ID_PREFIX). Stays small so same-MODEL fleets average ~75 items
# (enables sibling embeddings to do real work in the GNN).
MODEL_CATALOG = {
    "5G_ROUTER": [
        ("RTR-A1", "Cisco",   "PART-RTR-A1"),
        ("RTR-A2", "Cisco",   "PART-RTR-A2"),
        ("RTR-B1", "Juniper", "PART-RTR-B1"),
        ("RTR-B2", "Juniper", "PART-RTR-B2"),
    ],
    "ANTENNA": [
        ("ANT-C1", "Ericsson", "PART-ANT-C1"),
        ("ANT-C2", "Ericsson", "PART-ANT-C2"),
        ("ANT-D1", "Nokia",    "PART-ANT-D1"),
        ("ANT-D2", "Nokia",    "PART-ANT-D2"),
    ],
    "BASEBAND_UNIT": [
        ("BBU-E1", "Huawei",   "PART-BBU-E1"),
        ("BBU-E2", "Huawei",   "PART-BBU-E2"),
        ("BBU-F1", "Samsung",  "PART-BBU-F1"),
        ("BBU-F2", "Samsung",  "PART-BBU-F2"),
    ],
    "AMPLIFIER": [
        ("AMP-G1", "Qualcomm", "PART-AMP-G1"),
        ("AMP-G2", "Qualcomm", "PART-AMP-G2"),
    ],
    "TRANSCEIVER": [
        ("TRX-H1", "Mediatek", "PART-TRX-H1"),
        ("TRX-H2", "Mediatek", "PART-TRX-H2"),
    ],
    "FIREWALL": [
        ("FWL-J1", "Fortinet", "PART-FWL-J1"),
        ("FWL-J2", "Fortinet", "PART-FWL-J2"),
    ],
}

# Mix of equipment types installed on a tower. Sum >= EQUIPMENT_COUNT_TARGET
# after we sample roughly EQUIPMENT_PER_TOWER per tower.
TYPE_WEIGHTS = {
    "5G_ROUTER":     2,   # ~2 routers per tower
    "ANTENNA":       2,   # ~2 antennas
    "BASEBAND_UNIT": 1,
    "AMPLIFIER":     1,
    "TRANSCEIVER":   1,
    "FIREWALL":      1,
}

# 8 advisories on 7 distinct MODELs (one model gets two advisories of
# different types -- a realistic case). Severity grades 0.50-0.95.
ADVISORIES = [
    ("RTR-A2", "RECALL",         0.95, "2024-09-15"),
    ("BBU-E1", "DEFECT_BATCH",   0.80, "2024-08-01"),
    ("ANT-C1", "FIRMWARE_BUG",   0.65, "2024-10-22"),
    ("AMP-G2", "EOL",            0.55, "2024-11-05"),
    ("FWL-J1", "SECURITY_PATCH", 0.50, "2024-07-12"),
    ("TRX-H1", "RECALL",         0.75, "2024-10-30"),
    ("BBU-F2", "FIRMWARE_BUG",   0.60, "2024-09-01"),
    ("RTR-A2", "FIRMWARE_BUG",   0.60, "2024-11-20"),   # second advisory same model
]

FIRMWARE_VERSIONS = [
    "v1.0.4", "v1.2.7", "v1.3.0", "v2.0.1", "v2.1.3", "v2.4.0",
    "v3.0.0", "v1.5.8-OUTDATED", "v2.0.2-OUTDATED", "v1.1.0-OUTDATED",
]


def _equipment_id(i: int) -> str:
    return f"EQP-{i:05d}"


def _health_id(i: int) -> str:
    # Hex-like 8 chars -- matches existing pattern HLT-XXXXXXXX
    rng_local = np.random.default_rng(i + 1_000_000)
    return "HLT-" + "".join(f"{x:X}" for x in rng_local.integers(0, 16, size=8))


def _serial_number(rng) -> str:
    return "-".join(
        [
            "".join(f"{x:X}" for x in rng.integers(0, 16, size=8)),
            "".join(f"{x:X}" for x in rng.integers(0, 16, size=4)),
            f"{rng.integers(0, 999):03d}",
        ]
    )


def assign_equipment_to_towers(tower_ids: list[str], rng: np.random.Generator) -> list[dict]:
    """Distribute equipment across towers. Each tower gets a sample
    drawn from TYPE_WEIGHTS (with light Poisson noise) so the totals
    land near EQUIPMENT_COUNT_TARGET."""
    records: list[dict] = []
    next_eqp_id = 1

    for tower_id in tower_ids:
        # Allow modest variance: each "weight" is the expected count.
        for eqp_type, expected in TYPE_WEIGHTS.items():
            count = rng.poisson(expected)
            for _ in range(count):
                models = MODEL_CATALOG[eqp_type]
                model_choice = models[rng.integers(0, len(models))]
                records.append(
                    dict(
                        EQUIPMENT_ID=_equipment_id(next_eqp_id),
                        TOWER_ID=tower_id,
                        EQUIPMENT_TYPE=eqp_type,
                        PART_ID=model_choice[2],
                        MANUFACTURER=model_choice[1],
                        MODEL=model_choice[0],
                        FIRMWARE_VERSION=FIRMWARE_VERSIONS[rng.integers(0, len(FIRMWARE_VERSIONS))],
                    )
                )
                next_eqp_id += 1
    return records


def add_serials_and_install_dates(records: list[dict], rng: np.random.Generator) -> list[dict]:
    base = datetime(2022, 1, 1)
    for r in records:
        r["SERIAL_NUMBER"] = _serial_number(rng)
        # Install dates span 2022-01-01 to 2024-06-30
        offset_days = rng.integers(0, 911)
        r["INSTALL_DATE"] = (base + timedelta(days=int(offset_days))).strftime("%Y-%m-%d")
    return records


def firmware_outdated(version: str) -> int:
    return 1 if "OUTDATED" in version.upper() else 0


def synthesize_labels(records: list[dict], advisory_severity: dict, rng: np.random.Generator):
    """For each equipment, draw the five risk components, combine, set
    HEALTH_SCORE consistent with the health component, and derive
    AT_RISK + STATUS. The advisory signal dominates the linear part
    (0.35); a 2-hop neighbor signal (0.25) adds the tower-mate effect;
    a smooth three-way interaction (0.15) catches compound risk that no
    single threshold isolates.
    """
    n = len(records)

    adv_sev = np.array([advisory_severity.get(r["MODEL"], 0.0) for r in records])

    # 2-hop relational signal: max advisory severity among OTHER
    # equipment items on the same tower. This is the multi-hop pattern
    # the GNN learns via Equipment -> Tower -> Equipment message
    # passing -- "your tower-mate has a known-bad model, so your
    # operational risk is elevated even if your own model is clean."
    tower_to_indices: dict[str, list[int]] = {}
    for i, r in enumerate(records):
        tower_to_indices.setdefault(r["TOWER_ID"], []).append(i)

    neighbor_risk = np.zeros(n)
    for tower_id, idxs in tower_to_indices.items():
        # For each equipment on this tower, neighbor_risk = max advisory
        # severity among the OTHER equipment on the same tower.
        if len(idxs) <= 1:
            continue
        sevs = adv_sev[idxs]
        max_sev = sevs.max()
        # Equipment that itself has the max severity gets the
        # second-highest; everyone else gets the max.
        sorted_sevs = np.sort(sevs)[::-1]
        second_max = sorted_sevs[1] if len(sorted_sevs) > 1 else 0.0
        for j, i in enumerate(idxs):
            neighbor_risk[i] = second_max if adv_sev[i] >= max_sev - 1e-9 else max_sev

    # Health gap distribution depends on advisory presence:
    # - strong advisory (>=0.7): equipment LOOKS healthy (advisory
    #   drives risk on its own)
    # - mid advisory (0.4-0.7): wider spread (combined cases exist)
    # - no/weak advisory: occasional health-only failures
    health_gap = np.empty(n)
    for i in range(n):
        if adv_sev[i] >= 0.7:
            health_gap[i] = rng.beta(2, 18)    # peaked near 0.10
        elif adv_sev[i] >= 0.4:
            health_gap[i] = rng.beta(3, 7)     # peaked near 0.30
        else:
            health_gap[i] = rng.beta(2, 8)     # peaked near 0.20

    firmware_flag = np.array([firmware_outdated(r["FIRMWARE_VERSION"]) for r in records])
    noise = rng.uniform(0.0, 1.0, size=n)

    # Smooth three-way interaction: fires when advisory + health gap +
    # firmware-outdated all contribute. A SQL writer can approximate
    # the AND-of-thresholds pattern but not the smooth product. The
    # `firmware_flag + 0.3` shifts the firmware contribution so a 0/1
    # binary doesn't fully zero out the interaction term.
    three_way = adv_sev * health_gap * (firmware_flag + 0.3) * 4.0

    latent = (
        0.25 * adv_sev
      + 0.45 * neighbor_risk
      + 0.10 * health_gap
      + 0.05 * firmware_flag
      + 0.10 * three_way
      + 0.05 * noise
    )

    at_risk = (latent > 0.50).astype(int)
    status = np.where(
        latent > 0.70, "FAILING",
        np.where(latent > 0.50, "WARNING", "OPERATIONAL"),
    )
    health_score = np.clip(
        (1.0 - health_gap) + rng.normal(0, 0.02, size=n), 0.0, 1.0
    )

    for i, r in enumerate(records):
        r["LATENT_RISK"] = round(float(latent[i]), 3)
        r["ADVISORY_SEVERITY"] = float(adv_sev[i])
        r["NEIGHBOR_RISK"] = round(float(neighbor_risk[i]), 3)
        r["HEALTH_GAP"] = round(float(health_gap[i]), 3)
        r["HEALTH_SCORE"] = round(float(health_score[i]), 3)
        r["THREE_WAY"] = round(float(three_way[i]), 3)
        r["AT_RISK"] = int(at_risk[i])
        r["STATUS"] = str(status[i])
        r["FIRMWARE_OUTDATED"] = int(firmware_flag[i])

    return records


def build_health_table(records: list[dict], rng: np.random.Generator) -> pd.DataFrame:
    """One health snapshot per equipment. Continuous health metrics
    correlate weakly with latent_risk so no single column is a perfect
    predictor; HEALTH_SCORE is the strongest (still ~r=-0.4 vs AT_RISK).
    """
    rows = []
    for i, r in enumerate(records):
        risk = r["LATENT_RISK"]
        mtbf = float(np.clip(15000 * (1 - risk) + rng.normal(0, 3000), 100, 25000))
        failure_rate = float(np.clip(0.02 + 0.15 * risk + rng.normal(0, 0.03), 0.001, 0.5))
        temp = float(np.clip(45 + 8 * risk + rng.normal(0, 6), 25, 85))
        power = float(np.clip(1.2 + 1.0 * risk + rng.normal(0, 0.5), 0.3, 4.5))

        # Last failure date: more recent if risk is higher
        days_back = max(1, int(120 * (1 - risk) + rng.normal(0, 20)))
        last_failure = (datetime(2025, 11, 30) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        # Measurement date: recent; uniform over Nov-Dec 2025 for the demo
        meas_offset = int(rng.integers(0, 30))
        meas_date = (datetime(2025, 12, 1) + timedelta(days=meas_offset)).strftime("%Y-%m-%d")

        rows.append(
            dict(
                HEALTH_ID=_health_id(i),
                EQUIPMENT_ID=r["EQUIPMENT_ID"],
                MTBF_HOURS=int(mtbf),
                FAILURE_RATE=round(failure_rate, 3),
                LAST_FAILURE_DATE=last_failure,
                TEMPERATURE_AVG_C=round(temp, 1),
                POWER_CONSUMPTION_KW=round(power, 1),
                HEALTH_SCORE=r["HEALTH_SCORE"],
                MEASUREMENT_DATE=meas_date,
            )
        )
    return pd.DataFrame(rows)


def build_upgrade_options(tower_ids: list[str], rng: np.random.Generator) -> pd.DataFrame:
    """One row per (tower, tier). Cost/capacity bands match the
    distribution in the existing 360-row file so the MIP behaves
    comparably; with 250 towers we now have 750 options total."""
    rows = []
    for tid in tower_ids:
        # BRONZE: 2-4 Gbps,  $50k-$120k, 2-5 weeks
        rows.append(dict(
            TOWER_ID=tid,
            UPGRADE_TIER="BRONZE",
            CAPACITY_INCREASE_GBPS=int(rng.integers(2, 5)),
            COST_USD=int(rng.integers(50_000, 120_001)),
            INSTALL_WEEKS=int(rng.integers(2, 6)),
        ))
        # SILVER: 5-7 Gbps, $130k-$280k, 4-8 weeks
        rows.append(dict(
            TOWER_ID=tid,
            UPGRADE_TIER="SILVER",
            CAPACITY_INCREASE_GBPS=int(rng.integers(5, 8)),
            COST_USD=int(rng.integers(130_000, 280_001)),
            INSTALL_WEEKS=int(rng.integers(4, 9)),
        ))
        # GOLD: 8-12 Gbps, $290k-$520k, 8-16 weeks
        rows.append(dict(
            TOWER_ID=tid,
            UPGRADE_TIER="GOLD",
            CAPACITY_INCREASE_GBPS=int(rng.integers(8, 13)),
            COST_USD=int(rng.integers(290_000, 520_001)),
            INSTALL_WEEKS=int(rng.integers(8, 17)),
        ))
    return pd.DataFrame(rows)


def build_advisories() -> pd.DataFrame:
    return pd.DataFrame(ADVISORIES, columns=["MODEL", "ADVISORY_TYPE", "SEVERITY", "ISSUED_DATE"])


def report(eq_df: pd.DataFrame, hl_df: pd.DataFrame, adv_df: pd.DataFrame, upgrade_df: pd.DataFrame):
    print("=" * 60)
    print("Synthesized data summary")
    print("=" * 60)

    print(f"\n  Equipment:       {len(eq_df):>5}")
    print(f"  Health snapshots:{len(hl_df):>5}")
    print(f"  Advisories:      {len(adv_df):>5}")
    print(f"  Upgrade options: {len(upgrade_df):>5} ({upgrade_df['TOWER_ID'].nunique()} towers x 3 tiers)")

    print(f"\n  STATUS distribution:")
    print(eq_df["STATUS"].value_counts().to_string())
    print(f"  AT_RISK rate: {eq_df['AT_RISK'].mean():.1%}")

    print(f"\n  Unique MODELs: {eq_df['MODEL'].nunique()}")
    print(f"  Median equipment per model: {eq_df.groupby('MODEL').size().median():.0f}")

    # Compute correlations using eq_df for HEALTH_SCORE (the eq + health
    # tables share that column; using eq_df sidesteps the suffix
    # collision after merge). Other health columns come from hl_df.
    print(f"\n  Feature -> AT_RISK correlations (target: HEALTH_SCORE r ~ -0.4):")
    r = eq_df[["HEALTH_SCORE", "AT_RISK"]].corr().iloc[0, 1]
    print(f"    corr(HEALTH_SCORE, AT_RISK) = {r:+.3f}")
    hl_join = hl_df.merge(eq_df[["EQUIPMENT_ID", "AT_RISK"]], on="EQUIPMENT_ID")
    for col in ("MTBF_HOURS", "FAILURE_RATE", "TEMPERATURE_AVG_C", "POWER_CONSUMPTION_KW"):
        r = hl_join[[col, "AT_RISK"]].corr().iloc[0, 1]
        print(f"    corr({col}, AT_RISK) = {r:+.3f}")

    print(f"\n  Risk-source breakdown of AT_RISK equipment:")
    ar = eq_df[eq_df["AT_RISK"] == 1].copy()
    ar["RISK_SOURCE"] = "other / noise"
    # Order matters: assign the most-specific category first so each
    # equipment lands in exactly one bucket.
    ar.loc[ar["THREE_WAY"] > 0.8, "RISK_SOURCE"] = "three-way interaction"
    ar.loc[
        (ar["RISK_SOURCE"] == "other / noise")
        & (ar["NEIGHBOR_RISK"] > 0.5)
        & (ar["ADVISORY_SEVERITY"] < 0.3),
        "RISK_SOURCE",
    ] = "neighbor-driven (2-hop)"
    ar.loc[
        (ar["RISK_SOURCE"] == "other / noise")
        & (ar["ADVISORY_SEVERITY"] > 0.4)
        & (ar["HEALTH_GAP"] < 0.3),
        "RISK_SOURCE",
    ] = "advisory-only"
    ar.loc[
        (ar["RISK_SOURCE"] == "other / noise")
        & (ar["ADVISORY_SEVERITY"] > 0.3)
        & (ar["HEALTH_GAP"] > 0.25),
        "RISK_SOURCE",
    ] = "combined (advisory + health)"
    ar.loc[
        (ar["RISK_SOURCE"] == "other / noise")
        & (ar["ADVISORY_SEVERITY"] < 0.2)
        & (ar["HEALTH_GAP"] > 0.4),
        "RISK_SOURCE",
    ] = "health-only"
    print(ar["RISK_SOURCE"].value_counts().to_string())

    print(f"\n  SQL-vs-GNN comparison:")
    total_atrisk = int(eq_df["AT_RISK"].sum())

    # 1) Naive SQL: equipment columns only (health threshold).
    sql_naive = ((eq_df["AT_RISK"] == 1) & (eq_df["HEALTH_SCORE"] < 0.5)).sum()
    print(f"    Naive SQL (`WHERE health_score < 0.5`): "
          f"{sql_naive} / {total_atrisk} ({sql_naive/total_atrisk:.1%})")

    # 2) Join-aware SQL: also joins ModelAdvisory by MODEL.
    advised_models = set(adv_df["MODEL"].tolist())
    sql_joined = (
        (eq_df["AT_RISK"] == 1)
        & ((eq_df["HEALTH_SCORE"] < 0.5) | (eq_df["MODEL"].isin(advised_models)))
    ).sum()
    print(f"    Join-aware SQL (above + `OR model IN advised`): "
          f"{sql_joined} / {total_atrisk} ({sql_joined/total_atrisk:.1%})")

    # 3) GNN-only opportunity: AT_RISK items the join-aware SQL still misses.
    #    These are dominated by 2-hop neighbor-driven cases and smooth
    #    three-way interactions on non-advised models.
    gnn_only = total_atrisk - sql_joined
    print(f"    Remaining (only the GNN's multi-hop / interaction signal): "
          f"{gnn_only} ({gnn_only/total_atrisk:.1%})")


def main():
    rng = np.random.default_rng(SEED)

    # Anchor on existing cell_towers.csv -- we keep that file unchanged.
    cell_towers = pd.read_csv(DATA_DIR / "cell_towers.csv")
    tower_ids = cell_towers["TOWER_ID"].tolist()

    # Phase 1: generate equipment skeleton (id, type, model, manufacturer, firmware)
    records = assign_equipment_to_towers(tower_ids, rng)
    # If we missed the target, top up; if over, trim.
    while len(records) < EQUIPMENT_COUNT_TARGET:
        # Top up with extra antennas (the most common type)
        tid = tower_ids[rng.integers(0, len(tower_ids))]
        models = MODEL_CATALOG["ANTENNA"]
        mc = models[rng.integers(0, len(models))]
        records.append(dict(
            EQUIPMENT_ID=_equipment_id(len(records) + 1),
            TOWER_ID=tid, EQUIPMENT_TYPE="ANTENNA", PART_ID=mc[2],
            MANUFACTURER=mc[1], MODEL=mc[0],
            FIRMWARE_VERSION=FIRMWARE_VERSIONS[rng.integers(0, len(FIRMWARE_VERSIONS))],
        ))
    if len(records) > EQUIPMENT_COUNT_TARGET:
        records = records[:EQUIPMENT_COUNT_TARGET]

    # Phase 2: install dates + serial numbers
    records = add_serials_and_install_dates(records, rng)

    # Phase 3: label model -- AT_RISK, STATUS, HEALTH_SCORE
    advisory_sev = {m: sev for m, _, sev, _ in ADVISORIES}
    # Note: multiple advisories per model -> take the max severity. Build map:
    adv_max_sev: dict[str, float] = {}
    for m, _, sev, _ in ADVISORIES:
        adv_max_sev[m] = max(adv_max_sev.get(m, 0.0), sev)
    synthesize_labels(records, adv_max_sev, rng)

    # Phase 4: derived health table
    health_df = build_health_table(records, rng)

    # Phase 5: derived upgrade options for ALL towers
    upgrade_df = build_upgrade_options(tower_ids, rng)

    # Phase 6: advisories table
    adv_df = build_advisories()

    # Write CSVs. Equipment CSV keeps the original column order; we drop
    # the internal LATENT_RISK / ADVISORY_SEVERITY / HEALTH_GAP / etc.
    eq_df = pd.DataFrame(records)
    eq_df = eq_df[
        [
            "EQUIPMENT_ID", "TOWER_ID", "EQUIPMENT_TYPE", "PART_ID",
            "MANUFACTURER", "MODEL", "SERIAL_NUMBER", "INSTALL_DATE",
            "FIRMWARE_VERSION", "STATUS",
        ]
    ]
    eq_df.to_csv(DATA_DIR / "network_equipment.csv", index=False)
    health_df.to_csv(DATA_DIR / "equipment_health.csv", index=False)
    adv_df.to_csv(DATA_DIR / "model_advisories.csv", index=False)
    upgrade_df.to_csv(DATA_DIR / "tower_upgrade_options.csv", index=False)

    # Report (uses the full records list for diagnostics, not the trimmed CSV)
    full_df = pd.DataFrame(records)
    report(full_df, health_df, adv_df, upgrade_df)


if __name__ == "__main__":
    main()
