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

Predicting health-related behaviors like smoking status from medical and demographic data is a common tabular machine learning task. In practice, though, these behaviors are also shaped by social context: friends, family, and peers often influence one another. This template demonstrates how to model both individual attributes and social relationships with a Graph Neural Network (GNN), using the RelationalAI predictive reasoner to train a single end-to-end model.

The pipeline is intentionally minimal:

1. Load person-level attributes and relationship edges.
2. Build a graph where people are nodes and social connections are edges.
3. Define the feature configuration, including categorical and numerical properties.
4. Train a GNN to predict each person's smoking status.
5. Use both individual features and neighborhood structure during prediction.

The dataset consists of:

- **People** as nodes -- demographic and medical attributes per person.
- **Related** as edges -- pairs of people who are connected.
- **Binary labels** -- smoking status (0 / 1) for each person.

The GNN learns from both per-person features and graph structure, allowing information from connected individuals to influence each prediction.

**Start with `smoker_status_prediction_local.py`** -- it loads the bundled CSV data via `model.data()` and runs end-to-end without external Snowflake setup beyond the RelationalAI Native App.

**Then adapt `smoker_status_prediction.py`** -- the same pipeline pointed at Snowflake-hosted tables.

Both scripts train the GNN through the same RelationalAI Native App; the only difference is whether the source data is loaded from local CSVs or from Snowflake tables. The default `device="cuda"` works on a GPU-enabled RAI engine -- change it to `"cpu"` at the top of either script if your engine is CPU-only.

> [!IMPORTANT]
> The RelationalAI **predictive reasoner (GNN)** used in this template is in
> private preview.

## Who this is for

- Data scientists who want to leverage the relational structure of data stored across connected tables
- ML engineers learning the RelationalAI predictive reasoner workflow
- Health analytics teams interested in incorporating social or relational structure into predictive models

Assumes familiarity with Python and basic ML concepts (binary classification, train/val/test splits).

## What you'll build

- A graph model where rows of a `PEOPLE` table become nodes and rows of a `RELATED` edge list become edges.
- A `PropertyTransformer` that exposes 16 medical and demographic features.
- A binary-classification GNN trained to predict each person's smoking status.
- (Optional) A registered model in the Snowflake Model Registry that can be loaded and reused without retraining.

## What's included

- **Scripts**:
  - `smoker_status_prediction_local.py` -- **primary, runnable out of the box.** Loads CSVs from `data/` via `model.data()`.
  - `smoker_status_prediction.py` -- **reference pattern** for adapting the same pipeline to Snowflake-hosted tables.
- **Sample data** (`data/`):
  - `people.csv` -- 38,985 individuals with demographic and medical features.
  - `related.csv` -- 58,355 connection pairs between people.
  - `train.csv` / `validation.csv` / `test.csv` -- labeled splits with smoking status.

## Prerequisites

### Access

**To run the local demo (`smoker_status_prediction_local.py`)** you need a Snowflake account with the RelationalAI Native App. The bundled CSVs in `data/` ship with the template; GNN training runs on the RelationalAI engine, so the native app needs USAGE + CREATE EXPERIMENT / CREATE MODEL grants on the experiment schema (see the SQL block in [step 5 of the Quickstart](#quickstart)).

**To adapt to your own Snowflake pipeline (`smoker_status_prediction.py` as reference)** you'll additionally need the CSVs uploaded to Snowflake tables (or your own schema-equivalent dataset). Quote column names when creating the tables so spaces and parentheses are preserved (e.g. `"height(cm)"`, `"fasting blood sugar"`).

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`) >= 1.4.1

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
   Follow the interactive prompts (host platform, account, user, role, warehouse, etc.) -- your `raiconfig.toml` is generated automatically from the answers you provide.

5. Grant the RelationalAI Native App access to a schema for experiment artifacts. The local script uses `SMOKER_STATUS_PREDICTION.EXPERIMENTS` by default -- create those (or change the constants at the top of the script), update the `SET` statements below to match your database, schema, and Native App name, and run the following in a Snowflake SQL worksheet:
   ```sql
   SET db_name            = 'SMOKER_STATUS_PREDICTION';
   SET schema_experiments = 'SMOKER_STATUS_PREDICTION.EXPERIMENTS';
   SET app_name           = 'RELATIONALAI';   -- replace with your app name

   GRANT USAGE             ON DATABASE identifier($db_name)            TO APPLICATION identifier($app_name);
   GRANT USAGE             ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
   GRANT CREATE EXPERIMENT ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
   GRANT CREATE MODEL      ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
   ```

6. Run the local demo on the bundled CSVs:
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
3. Run:
   ```bash
   python smoker_status_prediction.py
   ```

## Template structure

```text
.
├── README.md                               # this file
├── pyproject.toml                          # dependencies
├── smoker_status_prediction_local.py       # primary: CSV-based script
├── smoker_status_prediction.py             # reference: Snowflake pipeline
└── data/
    ├── people.csv          # 38,985 rows, 17 columns
    ├── related.csv         # 58,355 (person1, person2) pairs
    ├── train.csv           # 31,187 (Id, smoking) rows
    ├── validation.csv      # 3,898 rows
    └── test.csv            # 3,899 rows
```

**Start here**: `smoker_status_prediction_local.py` (no external setup beyond Snowflake grants). Use `smoker_status_prediction.py` as the adaptation reference when you wire this pattern into your own Snowflake data.

## Sample data

The dataset contains medical and demographic attributes for a population of individuals in the `PEOPLE` table, along with a `RELATED` table of connected pairs. Connections were constructed so that linked individuals are more likely to share the same smoking status, giving the network a genuinely informative signal for the GNN.

- **people.csv** -- an `Id` identifier plus 16 medical/demographic features: `age`, `height(cm)`, `weight(kg)`, blood pressure (`systolic`, `relaxation`), `fasting blood sugar`, lipids (`Cholesterol`, `triglyceride`, `HDL`, `LDL`), `hemoglobin`, urinalysis (`Urine protein`, `serum creatinine`), liver enzymes (`AST`, `ALT`, `Gtp`), and a binary `dental caries` indicator.
- **related.csv** -- pairs of `Id`s representing connections between persons.
- **train / validation / test** -- split-specific `(Id, smoking)` rows where `smoking ∈ {0, 1}`.

## Model overview

### Key entities

- **People** (`Id`): individuals with demographic and medical attributes.
- **Related**: pairs of people, used as the edge list of the GNN graph.

### Pipeline stages

```text
People + Related (CSVs or Snowflake tables)
  → Build the graph: nodes as persons, self-referential edges People ↔ People (via Related)
  → Configure features: PropertyTransformer (continuous medical features + dental_caries category)
  → Define the task: Train / Validation / Test relationships
  → Train and predict: binary-classification GNN → predictions on the Test cohort
  → (Optional) Register and load the trained model
```

### Concepts

**People** -- individuals with demographic and medical attributes.

| Property | Type | Notes |
|---|---|---|
| `Id` | integer | Identifying; unique per person |
| `age` | integer | Age in years |
| `height(cm)` | integer | Height in centimeters |
| `weight(kg)` | integer | Weight in kilograms |
| `systolic` | integer | Systolic blood pressure |
| `relaxation` | integer | Diastolic blood pressure |
| `fasting blood sugar` | integer | Fasting blood glucose level |
| `Cholesterol` | integer | Total cholesterol |
| `triglyceride` | integer | Triglyceride level |
| `HDL` | integer | High-density lipoprotein |
| `LDL` | integer | Low-density lipoprotein |
| `hemoglobin` | float | Hemoglobin level |
| `Urine protein` | integer | Urine protein indicator |
| `serum creatinine` | float | Serum creatinine level |
| `AST` | integer | Aspartate aminotransferase (liver enzyme) |
| `ALT` | integer | Alanine aminotransferase (liver enzyme) |
| `Gtp` | integer | Gamma-glutamyl transferase (liver enzyme) |
| `dental caries` | integer | Binary indicator (0 / 1) |

**Related** -- pairs of connected people; used to construct edges in the GNN graph. No primary key.

| Property | Type | Notes |
|---|---|---|
| `person1` | integer | Foreign key into `People.Id` |
| `person2` | integer | Foreign key into `People.Id` |

**TrainTable / ValidationTable / TestTable** -- split tables joined to `People` by `Id` to build the train, validation, and test relationships. `TestTable.smoking` is held out from the model.

| Property | Type | Notes |
|---|---|---|
| `Id` | integer | Foreign key into `People.Id` |
| `smoking` | integer | Binary label (0 / 1); held out for `TestTable` |

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

Instantiate the GNN with the graph, the `PropertyTransformer`, and the Train / Validation relationships, fit it, then attach predictions over the held-out Test cohort to each `People` instance:

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

The bottom of each script has a commented-out block that registers the trained model in the Snowflake Model Registry, then loads it into a fresh `GNN` instance and predicts without retraining. Uncomment it if you want to register a model, load it back, and run predictions without retraining.

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
- **Register the model** for reuse: uncomment the bonus section at the bottom of either script.

## Troubleshooting

<details>
<summary>Predictions are all the same class</summary>

Check the class balance in `train.csv` -- if it's heavily skewed, consider re-sampling or training for more epochs with a lower learning rate. Also verify that the `RELATED` edges correlate with shared smoking status; without an informative network, the GNN reduces to a tabular model.
</details>

<details>
<summary>GNN training is very slow</summary>

GNN training runs on the RelationalAI engine you've provisioned. The `device` flag in the script picks which engine flavor to use -- `"cuda"` for GPU-enabled engines (default; significantly faster), `"cpu"` for CPU-only engines. If training is slow with `device="cuda"`, your engine may not actually have GPU; check the engine type or fall back to `"cpu"`.
</details>

<details>
<summary>Permissions error from RelationalAI native app</summary>

The native app needs USAGE on the database and CREATE EXPERIMENT / CREATE MODEL on the experiment schema. Run:

```sql
SET db_name            = '<db>';
SET schema_experiments = '<db>.<exp_schema>';
SET app_name           = 'RELATIONALAI';   -- replace with your app name

GRANT USAGE             ON DATABASE identifier($db_name)            TO APPLICATION identifier($app_name);
GRANT USAGE             ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
GRANT CREATE EXPERIMENT ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
GRANT CREATE MODEL      ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
```
</details>

<details>
<summary>rai init fails or connection errors</summary>

Ensure your Snowflake credentials are configured correctly and that the RAI Native App is installed on your account. Run `rai init` again and verify the connection settings.
</details>
