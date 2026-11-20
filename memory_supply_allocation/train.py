"""Train the deployed supplier-capability GNN and register its version.

Run after `rai models deploy --path model`:
    python train.py

`gnn.fit()` deploys the model if it changed, trains over the train and
validation tables the deployment installed, and registers the run as the
model and version that `reasoners.predictive.gnns.supplier_capability` names
in raiconfig.yaml.
"""

from model import HORIZON_END_PERIOD, gnn
from model.source import test_split_df, train_split_df, val_split_df


def main() -> None:
    if gnn is None:
        raise SystemExit("USE_PRECOMPUTED_FORECAST is set in model/reasoning.py: there is no GNN to train.")
    print("=" * 60)
    print("Stage 2: Training supplier-capability GNN (regression)")
    print("=" * 60)
    print(
        f"Split: train={len(train_split_df)} (periods -23..-4), "
        f"val={len(val_split_df)} (periods -3..0), "
        f"test={len(test_split_df)} (periods 1..{HORIZON_END_PERIOD})"
    )
    gnn.fit()


if __name__ == "__main__":
    main()
