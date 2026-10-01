"""Sample PaySim into the bundled mini subset used by fraud_detection_local.py.

One-time author-run script. The output CSVs (transactions/accounts/train/val/test)
are checked in alongside this script; re-run only to regenerate from a local
PaySim dump if the sampling strategy changes.

Source: https://www.kaggle.com/datasets/ealaxi/paysim1 (CC BY-SA 4.0),
     mirrored at https://huggingface.co/datasets/kohdified/synthetic-financial-data

Usage (from a shell with pandas + pyarrow available):
    # Download both PaySim parquet shards:
    mkdir -p /tmp/paysim
    curl -sL -o /tmp/paysim/0.parquet \
        "https://huggingface.co/api/datasets/kohdified/synthetic-financial-data/parquet/default/train/0.parquet"
    curl -sL -o /tmp/paysim/1.parquet \
        "https://huggingface.co/api/datasets/kohdified/synthetic-financial-data/parquet/default/train/1.parquet"
    python sample.py --source /tmp/paysim

Defaults produce ~16K transactions: all fraud rows (~8K) plus an equal number
of random non-fraud rows (~8K) in a 1:1 ratio, temporally split 70/15/15 by
the `step` column.
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

SEED = 42
# Class-balanced for CPU trainability on a bundled subset: take all fraud
# rows from the source, then an equal number of non-fraud rows sampled
# uniformly. Real PaySim has ~0.13% fraud — the README documents this gap.
TRAIN_FRAC, VAL_FRAC = 0.70, 0.15  # remainder is test

# Epoch for converting PaySim's integer `step` (hours 1..743) to a timestamp.
# Arbitrary anchor — only the hour offset matters for the GNN's time column.
EPOCH = datetime(2020, 1, 1)


def load_paysim(source_dir: Path) -> pd.DataFrame:
    shards = sorted(source_dir.glob("*.parquet"))
    if not shards:
        raise SystemExit(f"No *.parquet files under {source_dir}")
    return pd.concat([pd.read_parquet(p) for p in shards], ignore_index=True)


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """PaySim uses inconsistent casing (oldbalanceOrg vs oldbalanceDest).
    Normalize to snake_case and add a stable transaction_id + datetime."""
    df = raw.rename(columns={
        "step": "step",
        "type": "trans_type",
        "amount": "amount",
        "nameOrig": "name_orig",
        "oldbalanceOrg": "old_balance_orig",
        "newbalanceOrig": "new_balance_orig",
        "nameDest": "name_dest",
        "oldbalanceDest": "old_balance_dest",
        "newbalanceDest": "new_balance_dest",
        "isFraud": "is_fraud",
        "isFlaggedFraud": "is_flagged_fraud",
    })
    df["transaction_id"] = range(1, len(df) + 1)
    df["step_ts"] = [EPOCH + timedelta(hours=int(s)) for s in df["step"]]
    return df


def stratified_sample(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    fraud = df[df["is_fraud"] == 1]
    non_fraud = df[df["is_fraud"] == 0].sample(n=len(fraud), random_state=seed)
    return pd.concat([fraud, non_fraud], ignore_index=True).sample(
        frac=1.0, random_state=seed).reset_index(drop=True)


def temporal_split(sample: pd.DataFrame, train_frac: float, val_frac: float):
    ordered = sample.sort_values("step").reset_index(drop=True)
    n = len(ordered)
    n_train = int(n * train_frac)
    n_val = int(n * val_frac)
    train = ordered.iloc[:n_train].copy()
    val = ordered.iloc[n_train : n_train + n_val].copy()
    test = ordered.iloc[n_train + n_val :].copy()
    return train, val, test


def derive_accounts(sample: pd.DataFrame) -> pd.DataFrame:
    ids = pd.concat([sample["name_orig"], sample["name_dest"]]).unique()
    return pd.DataFrame({
        "account_id": ids,
        "account_type_prefix": [a[0] for a in ids],
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=Path("/tmp/paysim"),
                    help="Directory containing PaySim parquet shard(s)")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent,
                    help="Output directory for the mini CSVs")
    args = ap.parse_args()

    print(f"Loading PaySim shards from {args.source} ...")
    raw = load_paysim(args.source)
    print(f"  loaded {len(raw):,} rows  ({raw['isFraud'].sum():,} fraud)")

    print("Normalizing + sampling ...")
    norm = normalize(raw)
    sample = stratified_sample(norm, SEED)
    n_fraud = int(sample["is_fraud"].sum())
    print(f"  sampled {len(sample):,} rows  ({n_fraud} fraud, "
          f"{n_fraud/len(sample):.1%} class balance)")

    transactions = sample[[
        "transaction_id", "step", "step_ts", "trans_type", "amount",
        "name_orig", "old_balance_orig", "new_balance_orig",
        "name_dest", "old_balance_dest", "new_balance_dest",
        "is_flagged_fraud",
    ]]
    accounts = derive_accounts(sample)

    train, val, test = temporal_split(sample, TRAIN_FRAC, VAL_FRAC)
    print(f"  split  train={len(train):,}  val={len(val):,}  test={len(test):,}")

    args.out.mkdir(parents=True, exist_ok=True)
    transactions.to_csv(args.out / "transactions.csv", index=False)
    accounts.to_csv(args.out / "accounts.csv", index=False)
    # Train and val carry the label; test omits it so the GNN sees test as
    # held-out (matches the README's Snowflake SQL block where TEST is built
    # from `transaction_id` and `step_ts` only).
    for name, split_df in [("train", train), ("val", val)]:
        split_df[["transaction_id", "step", "step_ts", "is_fraud"]].to_csv(
            args.out / f"{name}.csv", index=False)
    test[["transaction_id", "step", "step_ts"]].to_csv(
        args.out / "test.csv", index=False)

    print(f"Wrote CSVs to {args.out}:")
    for p in sorted(args.out.glob("*.csv")):
        print(f"  {p.name}  ({p.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
