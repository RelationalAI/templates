"""Generate the bundled accounts.csv and transactions.csv for this template.

This is a one-time data-generation script, not part of the runner. The
template ships the deterministic CSV outputs of this script so users do
not need to run it. Re-run only if you change the planted-motif design
or want to regenerate with different parameters.

The output is a small synthetic AML ledger sized for a CSP solver demo:
60 named accounts (motif + decoy) plus 30 noise accounts (90 total), and
78 named transactions (motif + decoy) plus 60 noise transactions
(138 total). Three motifs are planted at known coordinates so each of
the three motif runners surfaces exactly the patterns they target. Decoy
accounts and transactions populate the remainder so each solver does
meaningful discrimination work, not just trivial pattern matching.

Planted motifs:

1. Two scatter-gather "butterflies" (the existing fixtures from prior
   versions, preserved verbatim): cluster bo=100 -> WireRecipientCorp,
   cluster bo=200 -> OffshoreLLC. Each butterfly fans 3 under-threshold
   deposits through 3 same-beneficial-owner hubs to a single recipient,
   with per-hub flow conservation in dollar amount.

2. One smurf-army deposit cluster: 5 source accounts with pairwise
   distinct beneficial owners and pairwise distinct jurisdictions all
   deposit small amounts to TargetMerchantX within a 60-minute window,
   summing to a known $27,000 target. Several decoys: dup-BO accounts
   that would fail pairwise distinctness, an out-of-window account, an
   over-target amount account.

3. One temporal-burst KYC-mix cluster: 4 retail-tier + 1 business-tier
   account across 4 distinct jurisdictions all transact to
   BurstTargetCorp within a 60-minute window. Decoys: a second
   business-tier account that would push the business count over cap,
   out-of-window accounts, and a single-account decoy.

Background noise: 60 random transactions among unrelated accounts to
make each solver do real discrimination work. Noise is deterministic
(seeded) so the bundled CSVs are reproducible.

Run: python generate.py (writes accounts.csv and transactions.csv into
this directory).
"""

import csv
import random
from pathlib import Path

# Determinism
SEED = 42
random.seed(SEED)

# ---------------------------------------------------------------------------
# Account roster
# ---------------------------------------------------------------------------
# Columns: id, name, bo_id, kyc_tier, jurisdiction.
# kyc_tier in {retail, business, private}. jurisdiction is a country/territory
# code; values are illustrative only (the constraints care about distinctness
# and category counts, not the specific codes).

NAMED_ACCOUNTS = [
    # --- Butterfly fixture (preserved from earlier template versions) ---
    (1, "SourceShellCorp", 600, "business", "US"),
    (2, "HubAccA1", 100, "retail", "US"),
    (3, "HubAccA2", 100, "retail", "US"),
    (4, "HubAccA3", 100, "retail", "US"),
    (5, "WireRecipientCorp", 700, "business", "US"),
    (6, "SecondShellCorp", 800, "business", "Cayman"),
    (7, "HubAccB1", 200, "retail", "Cayman"),
    (8, "HubAccB2", 200, "retail", "Cayman"),
    (9, "HubAccB3", 200, "retail", "Cayman"),
    (10, "OffshoreLLC", 900, "business", "Cayman"),
    (11, "IndividualX", 300, "retail", "US"),
    (12, "LegitBusiness", 400, "business", "US"),
    (13, "NearMissAcc", 100, "retail", "US"),
    (14, "PassthroughCorp", 500, "business", "US"),
    (15, "IndividualY", 400, "retail", "US"),
    (16, "AltCluster100A", 100, "retail", "US"),
    (17, "AltCluster100B", 100, "retail", "US"),
    (18, "AltCluster200A", 200, "retail", "Cayman"),
    (19, "NoiseAccA1", 1000, "retail", "US"),
    (20, "NoiseAccA2", 1000, "retail", "US"),
    (21, "NoiseAccB1", 1100, "retail", "UK"),
    (22, "NoiseAccB2", 1100, "retail", "UK"),
    (23, "SmallBizA", 1200, "business", "US"),
    (24, "SmallBizB", 1200, "business", "US"),
    (25, "SmallBizC", 1200, "business", "US"),
    (26, "IntermedA", 1300, "retail", "US"),
    (27, "IntermedB", 1300, "retail", "US"),
    (28, "HighVolA", 1400, "business", "US"),
    (29, "HighVolB", 1400, "business", "US"),
    (30, "SingleAcc1", 1500, "retail", "UK"),
    (31, "AnotherLegit", 400, "business", "US"),
    (32, "ThirdLegit", 400, "business", "US"),
    (33, "NoiseAccC1", 1600, "retail", "Singapore"),
    (34, "NoiseAccC2", 1600, "retail", "Singapore"),
    (35, "NoiseAccD1", 1700, "retail", "Germany"),
    (36, "NoiseAccD2", 1700, "retail", "Germany"),
    (37, "NoiseAccE1", 1800, "retail", "UK"),
    (38, "NoiseAccE2", 1800, "retail", "UK"),
    (39, "NoiseAccF1", 1900, "retail", "US"),
    (40, "NoiseAccG1", 2000, "retail", "US"),
    # --- Smurf-army cluster (variant 2): 5 distinct-BO sources -> single dest ---
    (41, "Pacific Receivables Inc", 2100, "business", "US"),
    (42, "Adrian Park", 1701, "retail", "US"),
    (43, "Mira Volkov", 1702, "retail", "UK"),
    (44, "Dimitri Solanki", 1703, "private", "Cayman"),
    (45, "Sofia Reyes", 1704, "retail", "Singapore"),
    (46, "Tomas Hellman", 1705, "retail", "Germany"),
    (47, "Lewis Holdings A", 1706, "retail", "US"),
    (48, "Lewis Holdings B", 1706, "retail", "UK"),
    (49, "Yara Costa", 1707, "retail", "US"),
    (50, "Helena Vargas", 1708, "retail", "US"),
    # --- KYC-burst cluster (variant 3): mixed retail/business across jurisdictions ---
    (51, "Continental Settlements LLC", 2200, "business", "US"),
    (52, "Trent Hayes", 2201, "retail", "US"),
    (53, "Samira Choudhury", 2202, "retail", "UK"),
    (54, "Diego Ramos", 2203, "retail", "Cayman"),
    (55, "Nikhil Tan", 2204, "retail", "Singapore"),
    (56, "Brookline Industries", 2205, "business", "US"),
    (57, "Newland Capital Inc", 2206, "business", "Germany"),
    (58, "Kira Stojanov", 2207, "retail", "Cayman"),
    (59, "Ravi Mehta", 2208, "retail", "US"),
    (60, "Emil Larson", 2209, "retail", "UK"),
]


def _make_noise_accounts(start_id: int, count: int) -> list:
    """Generate `count` noise accounts starting at id `start_id`."""
    tiers = ["retail", "business", "private"]
    jurisdictions = ["US", "UK", "Cayman", "Singapore", "Germany", "Switzerland", "Hong Kong"]
    out = []
    for i in range(count):
        acc_id = start_id + i
        # Each noise account gets its own bo_id (no ring-of-3+ that could
        # accidentally satisfy butterfly's same_bo_ic for hubs).
        bo_id = 3000 + i
        tier = random.choice(tiers)
        jur = random.choice(jurisdictions)
        out.append((acc_id, f"NoiseAcct{acc_id:03d}", bo_id, tier, jur))
    return out


# ---------------------------------------------------------------------------
# Transaction roster
# ---------------------------------------------------------------------------
# Columns: tx_id, src_id, dst_id, amount_dollars, ts_minutes.

NAMED_TRANSACTIONS = [
    # --- Butterfly motif #1 (cluster bo=100 -> WireRecipientCorp), ts 5-19 ---
    (1, 1, 2, 9000, 5),
    (2, 1, 3, 8500, 7),
    (3, 1, 4, 9500, 9),
    (4, 2, 5, 8980, 15),
    (5, 3, 5, 8475, 17),
    (6, 4, 5, 9420, 19),
    # --- Butterfly motif #2 (cluster bo=200 -> OffshoreLLC), ts 30-44 ---
    (7, 6, 7, 7000, 30),
    (8, 6, 8, 7500, 32),
    (9, 6, 9, 7800, 34),
    (10, 7, 10, 6950, 40),
    (11, 8, 10, 7480, 42),
    (12, 9, 10, 7780, 44),
    # --- Butterfly decoys: under threshold but fail conservation, owner, layer, etc. ---
    (13, 1, 11, 5000, 3),
    (14, 11, 5, 4500, 12),
    (15, 1, 5, 20000, 1),
    (16, 6, 10, 25000, 29),
    (17, 1, 13, 4000, 6),
    (18, 13, 5, 9500, 18),
    (19, 14, 5, 3000, 8),
    (20, 15, 10, 2500, 35),
    (21, 2, 15, 1000, 16),
    (22, 12, 5, 500, 2),
    (23, 7, 12, 500, 41),
    (24, 5, 11, 800, 25),
    (25, 1, 14, 2000, 4),
    (26, 1, 16, 8500, 11),
    (27, 16, 5, 7900, 21),
    (28, 1, 17, 9200, 13),
    (29, 17, 5, 8200, 23),
    (30, 6, 18, 7100, 36),
    (31, 18, 10, 6500, 46),
    # --- Bulk decoys / unrelated traffic ---
    (32, 23, 24, 2500, 50),
    (33, 24, 25, 1800, 52),
    (34, 25, 23, 1200, 54),
    (35, 26, 27, 3000, 56),
    (36, 27, 26, 2800, 58),
    (37, 28, 29, 15000, 60),
    (38, 29, 28, 18000, 62),
    (39, 19, 20, 5000, 65),
    (40, 20, 21, 4500, 67),
    (41, 21, 22, 3800, 69),
    (42, 33, 34, 4200, 71),
    (43, 34, 35, 5500, 73),
    (44, 35, 36, 5800, 75),
    (45, 37, 38, 3100, 77),
    (46, 38, 39, 2700, 79),
    (47, 39, 40, 1500, 81),
    (48, 1, 19, 3000, 4),
    (49, 19, 5, 4000, 15),
    (50, 6, 21, 3500, 33),
    (51, 21, 10, 4200, 38),
    (52, 1, 5, 18000, 2),
    (53, 6, 10, 14000, 28),
    (54, 12, 15, 11500, 40),
    (55, 31, 32, 12500, 45),
    (56, 5, 1, 500, 80),
    (57, 10, 6, 800, 82),
    (58, 13, 1, 1500, 84),
    (59, 2, 30, 300, 90),
    (60, 30, 5, 200, 92),
    # --- Smurf-army motif (variant 2): 5 distinct-BO sources -> TargetMerchantX ---
    # Sum = 5400 + 5450 + 5400 + 5350 + 5400 = 27000 (target). Window: 102-120 (max-min = 18 mins).
    (61, 42, 41, 5400, 102),
    (62, 43, 41, 5450, 105),
    (63, 44, 41, 5400, 110),
    (64, 45, 41, 5350, 115),
    (65, 46, 41, 5400, 120),
    # --- Smurf-army decoys ---
    # 47 and 48 share bo=1706 (would fail pairwise distinctness if both chosen).
    # Their amounts ($4500) differ from the real smurfs' $5350-5450 so substituting
    # one for any real smurf would also break the sum-equals-target constraint.
    (66, 47, 41, 4500, 108),
    (67, 48, 41, 4500, 112),
    # 49 transacts outside the 60-min window
    (68, 49, 41, 5400, 200),
    # 50 transacts in-window but at $9000, breaking the sum-equals-target constraint
    (69, 50, 41, 9000, 110),
    # --- KYC-burst motif (variant 3): 4 retail + 1 business -> BurstTargetCorp ---
    # Distribution: retail=4 (>= floor 4), business=1 (<= cap 1), 4 distinct
    # jurisdictions (US, UK, Cayman, Singapore). Window: 202-218 (max-min = 16 mins).
    (70, 52, 51, 4500, 202),
    (71, 53, 51, 5500, 205),
    (72, 54, 51, 4800, 210),
    (73, 55, 51, 5100, 215),
    (74, 56, 51, 4900, 218),
    # --- KYC-burst decoys ---
    # 57 is a second business-tier in window -- would break business <= 1 cap if chosen
    (75, 57, 51, 5000, 213),
    # 58 is retail in-window but only one account -- would fail count >= 5 if alone
    # We model "out of window" via large ts gap below. For variant clarity, this
    # row is in-window but selecting all 5 + 58 fails count == 5 only if we cap;
    # if we use count >= 5 floor, it is feasible as a 6-burst. We use exactly-5
    # in the runner to keep the demo clean.
    (76, 58, 51, 4500, 285),
    (77, 59, 51, 4500, 290),
    (78, 60, 51, 4500, 300),
]


def _make_noise_transactions(
    start_tx_id: int,
    count: int,
    account_ids: list[int],
    motif_account_ids: set[int],
    motif_target_ids: set[int],
    start_ts: int,
) -> list:
    """Generate background-noise transactions among non-motif accounts.

    Avoids: any tx into a motif target (preserves clean motif isolation
    in the solvers); any tx that would form an obvious 3-hub butterfly,
    smurf-army, or burst pattern incidentally.
    """
    safe_accounts = [a for a in account_ids if a not in motif_account_ids]
    out = []
    ts = start_ts
    for i in range(count):
        tx_id = start_tx_id + i
        # Pick src and dst from safe-account pool, avoiding self-loops.
        src = random.choice(safe_accounts)
        dst = random.choice(safe_accounts)
        while dst == src or dst in motif_target_ids:
            dst = random.choice(safe_accounts)
        # Mix of amounts: most under $10K, some over.
        if random.random() < 0.85:
            amount = random.randint(500, 9500)
        else:
            amount = random.randint(11000, 25000)
        # Spread timestamps; group some bursts to make the noise non-trivial.
        ts += random.randint(1, 8)
        out.append((tx_id, src, dst, amount, ts))
    return out


def main() -> None:
    here = Path(__file__).parent

    # Build account list: named + noise.
    n_noise_accounts = 30  # 40 named butterfly + 20 motif (smurf+burst) + 30 noise = 90
    noise_accounts = _make_noise_accounts(start_id=len(NAMED_ACCOUNTS) + 1, count=n_noise_accounts)
    all_accounts = NAMED_ACCOUNTS + noise_accounts

    # Build transaction list: named (motifs + decoys) + noise.
    motif_account_ids = {a[0] for a in NAMED_ACCOUNTS}
    motif_target_ids = {41, 51, 5, 10}  # destinations the solvers care about
    noise_account_ids = [a[0] for a in all_accounts]
    n_noise_tx = 60
    noise_tx = _make_noise_transactions(
        start_tx_id=len(NAMED_TRANSACTIONS) + 1,
        count=n_noise_tx,
        account_ids=noise_account_ids,
        motif_account_ids=motif_account_ids,
        motif_target_ids=motif_target_ids,
        start_ts=400,
    )
    all_tx = NAMED_TRANSACTIONS + noise_tx

    # Write CSVs.
    accounts_path = here / "accounts.csv"
    with accounts_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "bo_id", "kyc_tier", "jurisdiction"])
        for row in all_accounts:
            w.writerow(row)

    transactions_path = here / "transactions.csv"
    with transactions_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tx_id", "src_id", "dst_id", "amount_dollars", "ts_minutes"])
        for row in all_tx:
            w.writerow(row)

    print(f"Wrote {len(all_accounts)} accounts to {accounts_path}")
    print(f"Wrote {len(all_tx)} transactions to {transactions_path}")


if __name__ == "__main__":
    main()
