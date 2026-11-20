"""Train the deployed subscriber-retention GNN and register its version.

Run after `rai models deploy --path model`:
    python train.py

`gnn.fit()` deploys the model if it changed, trains over the train and
validation tables the deployment installed, and registers the run as the
model and version that `reasoners.predictive.gnns.churn_risk` names in
raiconfig.yaml.
"""

from model import gnn


def main() -> None:
    print("=" * 60)
    print("Predictive: subscriber churn-risk regression GNN")
    print("=" * 60)
    gnn.fit()


if __name__ == "__main__":
    main()
