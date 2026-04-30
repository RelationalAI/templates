---
title: "Smoker Status Prediction"
description: "Predict whether a person is a smoker from demographic and medical attributes plus a network of social connections, using a Graph Neural Network."
featured: false
experience_level: intermediate
industry: "Healthcare"
reasoning_types:
  - Predictive
tags:
  - GNN
  - Binary Classification
  - Node Classification
  - Healthcare
---

## What this template is for

Predicting health-related behaviors like smoking status from medical and demographic attributes alone is a familiar tabular-ML problem. But people don't make these choices in isolation -- friends, family, and peers influence them. This template shows how to use a Graph Neural Network (GNN) to combine **per-person features** with a **network of social connections** in a single model, trained with the RelationalAI predictive reasoner.

The pipeline is intentionally minimal:

1. **People** as nodes -- demographic and medical attributes per person.
2. **Related** as edges -- pairs of people who are connected.
3. **Binary classification** -- predict each person's smoking status (0 / 1).

The GNN learns from both per-person features and how those features propagate across the graph: two connected people who share many similar attributes nudge the model's prediction for both.

**Start with `smoker_status_prediction_local.py`** -- it loads the bundled CSV data via `model.data()`, trains on CPU, and runs end-to-end without external Snowflake setup beyond the RelationalAI Native App.

**Then adapt `smoker_status_prediction.py`** -- the same pipeline pointed at Snowflake-hosted tables, with the GNN configured for `cuda` training.

> [!IMPORTANT]
> The RelationalAI **predictive reasoner (GNN)** used in this template is in
> early access. The API surface (`GNN`, `PropertyTransformer`, task
> relationships) may still change between releases.

## Who this is for

- Data scientists exploring GNNs as an alternative to flat tabular models
- ML engineers learning the RelationalAI predictive reasoner workflow
- Health analytics teams interested in network-aware prediction

Assumes familiarity with Python and basic ML concepts (binary classification, train/val/test splits).

## What you'll build

- A graph model where rows of a `PEOPLE` table become nodes and rows of a `RELATED` edge list become edges.
- A `PropertyTransformer` that exposes 16 medical and demographic features.
- A binary-classification GNN trained to predict each person's smoking status.
- (Optional) A registered model in the Snowflake Model Registry that can be loaded and reused without retraining.

## What's included

- **Runners**:
  - `smoker_status_prediction_local.py` -- **primary, runnable out of the box.** Loads CSVs from `data/` via `model.data()` and trains on CPU.
  - `smoker_status_prediction.py` -- **reference pattern** for adapting the same pipeline to Snowflake-hosted tables (GPU recommended).
- **Sample data** (`data/`):
  - `people.csv` -- 38,985 individuals with demographic and medical features.
  - `related.csv` -- 58,355 connection pairs between people.
  - `train.csv` / `validation.csv` / `test.csv` -- labeled splits with smoking status.

## Prerequisites

### Access

**To run the local demo (`smoker_status_prediction_local.py`)** you need a Snowflake account with the RelationalAI Native App. The bundled CSVs in `data/` ship with the template; the GNN trains on CPU in a few minutes. Experiment artifacts are still written to a Snowflake schema, so the native app needs USAGE + CREATE EXPERIMENT / CREATE MODEL grants on that schema.

**To adapt to your own Snowflake pipeline (`smoker_status_prediction.py` as reference)** you'll additionally need:

- The CSVs uploaded to Snowflake tables (or your own schema-equivalent dataset). Quote column names when creating the tables so spaces and parentheses are preserved (e.g. `"height(cm)"`, `"fasting blood sugar"`).
- A GPU-enabled RAI engine for faster GNN training.

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.0.14

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/smoker_status_prediction.zip
   unzip smoker_status_prediction.zip
   cd smoker_status_prediction
   ```
   > [!TIP]
   > You can also download the template ZIP using the "Download ZIP" button at the top of this page.

2. Create venv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. Install:
   ```bash
   python -m pip install .
   ```

4. Configure:
   ```bash
   rai init
   ```

5. Grant the RelationalAI Native App access to a schema for experiment artifacts. The local runner uses `SMOKER_STATUS_PREDICTION.EXPERIMENTS` by default -- create those (or change the constants at the top of the script) and run:
   ```sql
   GRANT USAGE ON DATABASE SMOKER_STATUS_PREDICTION TO APPLICATION RELATIONALAI;
   GRANT USAGE ON SCHEMA SMOKER_STATUS_PREDICTION.EXPERIMENTS TO APPLICATION RELATIONALAI;
   GRANT CREATE EXPERIMENT ON SCHEMA SMOKER_STATUS_PREDICTION.EXPERIMENTS TO APPLICATION RELATIONALAI;
   GRANT CREATE MODEL ON SCHEMA SMOKER_STATUS_PREDICTION.EXPERIMENTS TO APPLICATION RELATIONALAI;
   ```

6. Run the local demo on the bundled CSVs (CPU, a few minutes):
   ```bash
   python smoker_status_prediction_local.py
   ```

### Adapting to your own Snowflake data

`smoker_status_prediction.py` shows the same pipeline against Snowflake-hosted tables. To adapt:

1. Upload the bundled CSVs (or your own equivalent dataset) to Snowflake. Quote column names in `CREATE TABLE` to preserve case and special characters:
   ```sql
   CREATE OR REPLACE TABLE SMOKER_STATUS_PREDICTION.DATA.PEOPLE (
       "Id" NUMBER, "age" NUMBER, "height(cm)" NUMBER, "weight(kg)" NUMBER,
       "fasting blood sugar" NUMBER, ...
   );
   ```
2. Edit the table references at the top of the script:
   ```python
   DATABASE = "YOUR_DB"
   SCHEMA = "YOUR_SCHEMA"           # holds PEOPLE and RELATED
   TASK_SCHEMA = "YOUR_TASK_SCHEMA" # holds TRAIN, VALIDATION, TEST
   GNN_EXP_DATABASE = "YOUR_DB"
   GNN_EXP_SCHEMA = "EXPERIMENTS"
   ```
3. Adjust the `PropertyTransformer` if your column names differ.
4. Run against a GPU-enabled RAI engine:
   ```bash
   python smoker_status_prediction.py
   ```

## Template structure

```text
.
├── README.md                               # this file
├── pyproject.toml                          # dependencies
├── smoker_status_prediction_local.py       # primary: CSV-based, CPU runner
├── smoker_status_prediction.py             # reference: Snowflake pipeline
└── data/
    ├── people.csv          # 38,985 rows, 17 columns
    ├── related.csv         # 58,355 (person1, person2) pairs
    ├── train.csv           # 31,187 (Id, smoking) rows
    ├── validation.csv      # 3,898 rows
    └── test.csv            # 3,899 rows
```

**Start here**: `smoker_status_prediction_local.py` (CPU, no external setup beyond Snowflake grants). Use `smoker_status_prediction.py` as the adaptation reference when you wire this pattern into your own Snowflake data.

## Sample data

The dataset is based on the [Smoker Status Prediction](https://www.kaggle.com/datasets/gauravduttakiit/smoker-status-prediction) Kaggle dataset, augmented with a synthetic `RELATED` edge list. Pairs of people in `RELATED` were generated by randomly pairing individuals, with a higher probability assigned to pairs where both share the same smoking status. The network signal is therefore genuinely informative.

- **people.csv** -- 16 medical/demographic features: `age`, `height(cm)`, `weight(kg)`, blood pressure (`systolic`, `relaxation`), `fasting blood sugar`, lipids (`Cholesterol`, `triglyceride`, `HDL`, `LDL`), `hemoglobin`, urinalysis (`Urine protein`, `serum creatinine`), liver enzymes (`AST`, `ALT`, `Gtp`), and a binary `dental caries` indicator.
- **related.csv** -- pairs of `Id`s representing connections.
- **train / validation / test** -- split-specific `(Id, smoking)` rows where `smoking ∈ {0, 1}`.

## Model overview

### Key entities

- **People** (`Id`): individuals with demographic and medical attributes.
- **Related**: pairs of people, used as an edge bridge in the GNN graph.

### Pipeline stages

```text
People + Related (CSVs or Snowflake tables)
  → Self-referential edge: People ↔ People (via Related)
  → PropertyTransformer (continuous medical features + dental_caries category)
  → Binary classification GNN
  → Predictions on the Test cohort
```

### Concepts

**People** -- domain entity with an `Id` candidate key and 16 medical and demographic features.

**Related** -- edge bridge with two foreign keys (`person1`, `person2`) into `People.Id`. No primary key; only used to construct edges.

**TrainTable / ValidationTable / TestTable** -- split tables joined to `People` by `Id` to build the train, validation, and test relationships.

## How it works

### 1. Build the graph

Each row of `Related` defines a directed edge from one `People` instance to another. Because both endpoints are the same concept, the destination uses `.ref()`:

```python
PeopleRef = People.ref()
model.define(Edge.new(src=People, dst=PeopleRef)).where(
    People.Id == Related.person1,
    PeopleRef.Id == Related.person2,
)
```

### 2. Configure features

`PropertyTransformer` lists the medical and demographic features as continuous, treats the binary `dental caries` indicator as a category, and drops the `Id` so it isn't fed into the model:

```python
pt = PropertyTransformer(
    continuous=[
        People.age,
        getattr(People, "height(cm)"),
        getattr(People, "weight(kg)"),
        ...
    ],
    category=[getattr(People, "dental caries")],
    drop=[People.Id],
)
```

The `getattr()` calls handle column names with special characters (spaces, parentheses) that aren't valid Python identifiers. The schema is preserved as-is so the same names work in Snowflake queries against the underlying tables.

### 3. Define the task

A simple node-classification task: each labeled row pairs a `People` instance with its smoking status. The `Test` relationship omits the label since it's held out.

```python
Train = Relationship(f"{People} has {Any:smoking}")
model.define(Train(People, TrainTable.smoking)).where(
    People.Id == TrainTable.Id
)

Test = Relationship(f"{People}")
model.define(Test(People)).where(
    People.Id == TestTable.Id
)
```

### 4. Train and predict

```python
gnn = GNN(
    exp_database=GNN_EXP_DATABASE, exp_schema=GNN_EXP_SCHEMA,
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Validation,
    task_type="binary_classification", eval_metric="roc_auc",
    device="cuda", n_epochs=5, lr=0.005, train_batch_size=256,
)
gnn.fit()
People.predictions = gnn.predictions(domain=Test)
```

### 5. (Optional) Register and load

The bottom of each runner has a commented-out block that registers the trained model in the Snowflake Model Registry, then loads it into a fresh `GNN` instance and predicts without retraining. Uncomment it after you've verified the pipeline works end-to-end.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own equivalent files (people, edges, splits). Column names need to match the `PropertyTransformer`, or you'll need to edit the transformer.
- For Snowflake adaptation, edit the `DATABASE`, `SCHEMA`, `TASK_SCHEMA`, and `GNN_EXP_*` constants at the top of `smoker_status_prediction.py`.

### Tune the model

- `n_epochs` -- increase for better convergence on a larger dataset.
- `lr` -- lower if training loss bounces.
- `eval_metric` -- switch to `"accuracy"` or `"f1"` if those metrics suit your problem better.
- `device` -- use `"cuda"` for faster training on a GPU-enabled engine.

For the full hyperparameter list, see the [Configure a GNN](https://docs.relational.ai/build/guides/reasoning/predictive/configure-a-GNN) guide.

### Extend the model

- **Add categorical demographics** (e.g. occupation, income bracket): list them under `category=[...]` in the `PropertyTransformer`.
- **Try a multiclass task**: if your label has more than two values (e.g. never / light / heavy smoker), change `task_type="multiclass_classification"` and use `eval_metric="macro_f1"` or `"accuracy"`.
- **Register the model** for reuse: uncomment the bonus section at the bottom of either runner.

## Troubleshooting

<details>
<summary>Predictions are all the same class</summary>

Check the class balance in `train.csv` -- if it's heavily skewed, consider re-sampling or training for more epochs with a lower learning rate. Also verify that the `RELATED` edges correlate with shared smoking status; without an informative network, the GNN reduces to a tabular model.
</details>

<details>
<summary>GNN training fails or is very slow</summary>

- For the Snowflake runner, ensure a GPU-enabled engine is available; CPU training on the full dataset is significantly slower.
- For the local runner, the bundled CSVs are sized for CPU runs (a few minutes on modern hardware). If it hangs, check that `device="cpu"` is set.
</details>

<details>
<summary>Snowflake column-name error: "concept has no field"</summary>

Snowflake uppercases unquoted identifiers by default. If you created the tables with unquoted column names, the script's `getattr(People, "fasting blood sugar")` references won't match. Either quote column names when creating the tables, or rename the columns to underscore-separated lowercase variants (e.g. `fasting_blood_sugar`) and update the `PropertyTransformer` accordingly.
</details>

<details>
<summary>Permissions error from RelationalAI native app</summary>

The native app needs USAGE on the database and CREATE EXPERIMENT / CREATE MODEL on the experiment schema. Run:

```sql
GRANT USAGE ON DATABASE <db> TO APPLICATION RELATIONALAI;
GRANT USAGE ON SCHEMA <db>.<exp_schema> TO APPLICATION RELATIONALAI;
GRANT CREATE EXPERIMENT ON SCHEMA <db>.<exp_schema> TO APPLICATION RELATIONALAI;
GRANT CREATE MODEL ON SCHEMA <db>.<exp_schema> TO APPLICATION RELATIONALAI;
```
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>
