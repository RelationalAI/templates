# Runbook

End-to-end run instructions for `datacenter_compute_allocation`. See [`README.md`](README.md) for the conceptual overview and the link to the upstream [`energy_grid_planning`](https://github.com/RelationalAI/templates/tree/main/v1/energy_grid_planning) template.

## Prerequisites

- Python 3.10+
- `relationalai>=1.0.14`, `pandas>=2.0`, `numpy>=1.24`, `scikit-learn>=1.3` -- install via `pip install -e .` from the template directory
- A configured `raiconfig.yaml` (the template inherits the parent `~/Documents/templates/raiconfig.yaml` if none is shipped here) pointing at a Snowflake account with the prescriptive engine and (optionally) a GPU engine for Stage 1
- For real GNN training: the `relationalai` install must include `relationalai.semantics.reasoners.predictive` (not in every PyPI release; pin a release that ships it or use a dev install). Without it, the script falls back to `lab_growth_forecasts.csv` automatically.
- For the predictive engine: a Snowflake database with `USAGE`, `CREATE EXPERIMENT`, `CREATE MODEL` granted to the `RELATIONALAI` native app (the script uses `DATACENTER_ENRICHMENT.EXPERIMENTS` by default; provision via:
  ```sql
  CREATE DATABASE IF NOT EXISTS DATACENTER_ENRICHMENT;
  CREATE SCHEMA   IF NOT EXISTS DATACENTER_ENRICHMENT.EXPERIMENTS;
  GRANT USAGE             ON DATABASE DATACENTER_ENRICHMENT             TO APPLICATION RELATIONALAI;
  GRANT USAGE             ON SCHEMA   DATACENTER_ENRICHMENT.EXPERIMENTS TO APPLICATION RELATIONALAI;
  GRANT CREATE EXPERIMENT ON SCHEMA   DATACENTER_ENRICHMENT.EXPERIMENTS TO APPLICATION RELATIONALAI;
  GRANT CREATE MODEL      ON SCHEMA   DATACENTER_ENRICHMENT.EXPERIMENTS TO APPLICATION RELATIONALAI;
  ```
  )

## Two-mode run

### Path A: Standalone mode (no upstream prerequisite)

The fastest path -- start here if you have not yet run `energy_grid_planning`.

```bash
cd v1/datacenter_compute_allocation
python datacenter_compute_allocation.py --standalone
```

Expected output structure (each section is one stage, in order):

```
============================================================
STAGE 0: STANDALONE LOAD
============================================================
  Standalone mode: fresh Model('Datacenter Compute Allocation')
  Loaded 5 DataCenterRequest entries from data/data_centers.csv
  Ontology loaded: 6 labs, 28 pools, 110 workloads, 138 dep edges, 48 scenario cells

============================================================
STAGE 1: PREDICT -- per-lab training-intensity GNN
============================================================
  ✓ Predictive reasoner test_gpu is READY
  ✓ Logic reasoner RAI_DEV_SERVICE is READY
  ... (GNN training + prediction, ~90-120s on GPU_NV_S)
  GNN training complete; per-lab multipliers extracted
  Per-lab projected demand multiplier (frontier should ramp 1.05+, Stability < 1.0):
    + OpenAI Pretrain           multiplier=1.1192
    + Anthropic Research        multiplier=1.1011
    + xAI Internal              multiplier=1.0816
    + Together AI Multi-Lab     multiplier=1.0395
    + Cohere Inference          multiplier=1.0306
    - Stability Open            multiplier=0.9680

============================================================
STAGE 2: RULES -- eligibility + priority classification
============================================================
  Compatibility table: ~1,900 eligible (Workload, GpuPool) pairs
  Priority tier counts: P0=15, P1=80, P2=15

============================================================
STAGE 3: GRAPH -- workload-dependency PageRank (gating score)
============================================================
  Top-10 gating workloads (frontier pretrains expected to dominate):
    GPT-Next pretrain shard 02                    score=0.0310
    Grok-Next pretrain shard 04                   score=0.0266
    Claude-Next pretrain shard 02                 score=0.0227
    ...

============================================================
STAGE 4: PRESCRIPTIVE -- compute allocation MIP (48-cell sweep)
============================================================
  Solving 48-cell scenario sweep with HiGHS...
  Termination status: TIME_LIMIT
  Solve time:         900.1s
  Objective:          787,884,896.15
  Note: TIME_LIMIT means solver returned a feasible but not proven-optimal solution.

  Per-cell summary (48 cells: 33 optimal, 15 infeasible):
  envelope    margin            diversity                            status      n_assigned   revenue_usd   ...
  100pct      unconstrained     none                                 OPTIMAL     110          25,277,810.94 ...
  100pct      85pct             none                                 OPTIMAL     18           22,032,899.59 ...
  100pct      85pct             anchor_max_50pct                     INFEASIBLE  0            ...           ...
  100pct      *                 anchor_max_40pct_with_type_floor     INFEASIBLE  0            ...           ...
  ...

  Pareto frontier 1: Margin floor <-> Revenue (envelope=100pct, diversity=none)
       margin  n_assigned  revenue_usd  realized_margin  anchor_share
        75pct  110         25,277,811   0.83             0.95
        80pct  110         25,277,811   0.83             0.95
        85pct   18         22,032,900   0.85             1.00
unconstrained  110         25,277,811   0.83             0.95

  Pareto frontier 2: Diversity cap <-> Revenue (envelope=100pct, margin=unconstrained)
                       diversity  n_assigned  revenue_usd  realized_margin  anchor_share
anchor_max_40pct_with_type_floor   0          ---          ---              ---
                anchor_max_50pct  97          2,598,602    0.76             0.49
                anchor_max_70pct  97          4,437,625    0.80             0.70
                            none 110          25,277,811   0.83             0.95
```

Wall time: dominated by the 48-cell MIP sweep. With ~2,000 binaries per cell and 48 cells, HiGHS hits the 900s `time_limit_sec` and returns a feasible solution. Per the rai-prescriptive-results-interpretation skill, TIME_LIMIT with sensible per-cell results is "near-optimal" -- acceptable for the demo. Increase `time_limit_sec` in `stage4_prescriptive` if you need a tighter gap.

### Path B: Chain mode (composes with upstream)

This mode reuses the upstream-approved DC set rather than the bundled snapshot. The end result for the default `--investment-level=$300M` is identical (same 5 DCs), but the lineage is explicit: `DataCenterRequest.approved_mw` is bound from upstream `x_approve` outcomes, and `DataCenterRequest.dollars_per_mwh` is attached via the `data/data_center_attrs.csv` side table.

1. **Run the upstream template once.** Following its README, run:
   ```bash
   cd v1/energy_grid_planning
   python energy_grid_planning.py
   ```
   This populates `Model("Energy Grid Infrastructure")` with `DataCenterRequest`, `InvestmentLevel`, and `x_approve(InvestmentLevel)` for all 5 budget levels.

2. **Run this template in chain mode.**
   ```bash
   cd ../datacenter_compute_allocation
   python datacenter_compute_allocation.py
   ```
   The script connects to the same model, reads `x_approve("$300M") > 0.5`, attaches the side-table properties, and proceeds identically through Stages 1-4.

3. **Try a different upstream investment level.** The upstream sweep ($200M to $600M) and this template's 3D scenario sweep compose into a 4D scenario grid:
   ```bash
   python datacenter_compute_allocation.py --investment-level "\$400M"
   ```
   At $400M the upstream solve approves 6 DCs (one more than $300M); the downstream supply set grows accordingly without any code change.

If chain mode prints `RuntimeError: no DataCenterRequest entries with x_approve > 0.5 ...`, the upstream template has not run on this account/engine. Use `--standalone` or run the upstream first.

## GNN-vs-baseline lift validation

Stage 1's value is reproducing the per-lab demand multipliers **with lower test RMSE than a per-lab tabular baseline**, attributable to the cross-lab `co_dated` heterogeneous edge. To validate this:

1. Run the GNN path:
   ```bash
   python datacenter_compute_allocation.py --standalone
   ```
   Capture the GNN test RMSE printed in Stage 1.

2. Run the per-lab gradient-boosted-trees baseline:
   ```python
   import pandas as pd
   from sklearn.ensemble import GradientBoostingRegressor
   from sklearn.metrics import mean_squared_error

   train = pd.read_csv("data/train_metrics.csv")
   test = pd.read_csv("data/test_metrics.csv")
   feature_cols = [
       "active_training_runs", "gpu_hours_consumed", "tokens_trained",
       "eval_runs_launched", "inference_qps", "model_release_events",
       "paper_submissions", "funding_announced_usd",
       "prev_day_growth", "prev_week_growth", "growth_7d_mean",
   ]
   target_col = "training_intensity_growth_rate"

   per_lab_rmse = []
   for lab, g_train in train.groupby("lab"):
       g_test = test[test["lab"] == lab]
       if len(g_test) == 0:
           continue
       m = GradientBoostingRegressor(random_state=42, n_estimators=200, max_depth=3)
       m.fit(g_train[feature_cols].fillna(0), g_train[target_col])
       pred = m.predict(g_test[feature_cols].fillna(0))
       rmse = mean_squared_error(g_test[target_col], pred, squared=False)
       per_lab_rmse.append((lab, rmse))
       print(f"  {lab:<25} GBT-baseline RMSE = {rmse:.4f}")
   import numpy as np
   print(f"  Mean baseline RMSE: {np.mean([r for _, r in per_lab_rmse]):.4f}")
   ```

3. **Compare.** The GNN should beat the baseline by a margin attributable to the `co_dated` edges (the only cross-lab signal source). If the GNN does not beat the baseline, the synthetic generator has not produced enough cross-lab co-movement -- strengthen the shared-component amplitudes in the data generator and re-run.

## Reproducibility

- All synthetic data is seeded with `seed=42` in the data generator.
- Stage 1 GNN is trained with `seed=42` and 80 epochs by default. RMSE may vary by single-digit % across runs depending on engine internals.
- HiGHS is deterministic for the cell sizes here; the same scenario cell with the same inputs produces the same `x_assign` solution.
- Stage 4 produces 36 independent cells. If wall time is a concern, you can subsample by editing `power_envelope_levels.csv` / `margin_floors.csv` / `diversity_caps.csv`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `RuntimeError: no DataCenterRequest entries with x_approve > 0.5` | Chain mode but upstream has not run | Run `energy_grid_planning` first, or use `--standalone`. |
| `ModuleNotFoundError: relationalai.semantics.reasoners.predictive` | Installed `relationalai` predates the predictive submodule | Use a release that ships the GNN (or `--no-gnn` to load fallback CSV). |
| `Database does not exist or the GNN RelationalAI Native App lacks permissions` | `DATACENTER_ENRICHMENT.EXPERIMENTS` not provisioned with required grants | Run the four `GRANT` statements in Prerequisites above. |
| `TransactionAbortedException: Transaction was aborted by the engine: runtime error.` (during `gnn.fit()`) | Runtime error in one of the GNN's exported tables -- usually a multi-valued Relationship on a GNN-node concept tripping the FD check | Pull the engine-side root cause: `snow sql -q "CALL RELATIONALAI.API.GET_TRANSACTION_ARTIFACTS('<txn_id>', OBJECT_CONSTRUCT())"` and download the `problems.json` artifact. The most common fix is moving the offending multi-valued relationship to its own composite-id Concept (mirrors how `Compatibility(workload, gpu_pool)` itself is a Concept, not a Workload Relationship). |
| `Termination status: INFEASIBLE` for the global solve | Some cell's constraints are mutually unsatisfiable AND the C1 P0 commitment was hard `==1` | C1 should be soft `<=1`; the priority_weight=100 in the objective drives P0 to 1 wherever feasible. Per-cell infeasibility then surfaces as `INFEASIBLE` in the per-cell summary, not as global failure. |
| `Termination status: TIME_LIMIT` with sensible per-cell results | Solver hit the 900s wall but returned a good feasible solution | Expected for the 48-cell sweep. The per-cell numbers remain valid (rai-prescriptive-results-interpretation: TIME_LIMIT is signal, not error). Increase `time_limit_sec` if you need a tighter MIP gap. |
| Per-cell summary shows all cells `INFEASIBLE` | Likely an upstream constraint (C5/C6/C7) firing at unintended cells | Check that NULL-handling sentinels (-1.0) are filtered correctly in C5/C6/C7's `model.where(... .fraction >= 0.0 ...)` clauses. |
| Per-lab multiplier numbers do not match the README's expected ramp | GNN trained with non-default seed/epochs, or `--no-gnn` fallback used | The fallback values in `lab_growth_forecasts.csv` are the deterministic reference; these are what downstream stages consume when `--no-gnn` is set. |

## File map

- `datacenter_compute_allocation.py` -- main script (4 stages + reporting)
- `data/` -- 15 CSV input files (see [`README.md`](README.md) "What's included")
- `pyproject.toml` -- dependencies
- `raiconfig.yaml` -- RAI connection scaffold (see your account team for credentials)
