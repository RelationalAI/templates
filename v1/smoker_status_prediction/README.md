---
title: "Smoker Status Prediction"
description: "Predict whether a person is a smoker from demographic and medical attributes plus a network of social connections."
featured: false
experience_level: intermediate
industry: "Healthcare & Life Sciences"
reasoning_types:
  - Predictive
tags:
  - Graph Neural Network (GNN)
  - Binary Classification
  - Node Classification
  - Healthcare
---

## What this template is for

Predicting health-related behaviors like smoking status from medical and demographic data is a common tabular machine learning task. In practice, though, these behaviors are also shaped by social context: friends, family, and peers often influence one another. This template demonstrates how to model both individual attributes and social relationships with a Graph Neural Network (GNN), using the RelationalAI **Predictive** reasoner to train a single end-to-end model.

## Who this is for

- Data scientists who want to leverage the relational structure of data stored across connected tables
- ML engineers learning the RelationalAI **Predictive** reasoner workflow
- Health analytics teams interested in incorporating social or relational structure into predictive models

Assumes familiarity with Python and basic ML concepts (binary classification, train/val/test splits).

## What you'll build

- A graph model where rows of a `PEOPLE` table become nodes and rows of a `RELATED` edge list become edges.
- A `PropertyTransformer` that exposes 17 medical and demographic features (16 continuous + 1 binary category).
- A binary-classification GNN trained to predict each person's smoking status.
- (Optional) A registered model in the Snowflake Model Registry that can be loaded and reused without retraining.

## What's included

- **Scripts**:
  - `smoker_status_prediction_local.py` -- **primary, runnable out of the box.** Loads CSVs from `data/` via `model.data()`.
  - `smoker_status_prediction.py` -- **reference pattern** for adapting the same pipeline to Snowflake-hosted tables.
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the script itself.
- **Sample data** (`data/`) -- bundled demo dataset for end-to-end runs; predictions are illustrative of the GNN methodology, not clinically meaningful (see [Sample data](#sample-data) for what's real vs. constructed):
  - `people.csv` -- 38,984 individuals with demographic and medical features.
  - `related.csv` -- 58,355 connection pairs between people.
  - `train.csv` / `validation.csv` / `test.csv` -- labeled splits with smoking status.

## Prerequisites

### Access

**To run the local demo (`smoker_status_prediction_local.py`)** you need a Snowflake account with the RelationalAI Native App. The bundled CSVs in `data/` ship with the template; GNN training runs on the RelationalAI engine, so the native app needs USAGE + CREATE EXPERIMENT / CREATE MODEL grants on the experiment schema (see the SQL block in [step 5 of the Quickstart](#quickstart)).

**To adapt to your own Snowflake pipeline (`smoker_status_prediction.py` as reference)** you'll additionally need the CSVs uploaded to Snowflake tables (or your own schema-equivalent dataset). Quote column names when creating the tables so spaces and parentheses are preserved (e.g. `"height(cm)"`, `"fasting blood sugar"`).

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai[gnn] == 1.8`)

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

   After `rai init` generates the config file, add the following to your `raiconfig.yaml`:

   ```yaml
   data:
       ensure_change_tracking: true
   ```

5. Grant the RelationalAI Native App access to a schema for experiment artifacts. The local script uses `SMOKER_STATUS_PREDICTION.EXPERIMENTS` by default (or change the constants at the top of the script). Update the `SET` statements below to match your database, schema, and Native App name, then run the following in a Snowflake SQL worksheet:
   ```sql
   SET db_name            = 'SMOKER_STATUS_PREDICTION';
   SET schema_experiments = 'SMOKER_STATUS_PREDICTION.EXPERIMENTS';
   SET app_name           = 'RELATIONALAI';   -- replace with your app name

   CREATE DATABASE IF NOT EXISTS identifier($db_name);
   CREATE SCHEMA   IF NOT EXISTS identifier($schema_experiments);

   GRANT USAGE             ON DATABASE identifier($db_name)            TO APPLICATION identifier($app_name);
   GRANT USAGE             ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
   GRANT CREATE EXPERIMENT ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
   GRANT CREATE MODEL      ON SCHEMA   identifier($schema_experiments) TO APPLICATION identifier($app_name);
   ```

6. Run the local demo on the bundled CSVs:
   ```bash
   python smoker_status_prediction_local.py
   ```

### Expected output (abbreviated)

Real numbers from a verified end-to-end run on the bundled CSVs (`smoker_status_prediction_local.py`). Dataset shape: **38,984 People** with **58,355 Related edges**, split into **31,187 train / 3,898 validation / 3,899 test** rows. Exact predicted probabilities shift slightly with numerical noise; metric values are stable within a few hundredths.

```text
============================================================
PREDICTIVE: Smoker status binary classification
============================================================

=== Start GNN Training ===
  ✓ Step 1 completed (4.77s)     # prepare trainer configuration
  ✓ Step 2 completed (16.65s)    # prepare dataset and GNN tables
  ✓ Step 3 completed (31.29s)    # submit training job and stream logs
=== GNN Training Complete (52.71s) ===

=== Start GNN Prediction ===
  ✓ Step 1 completed (5.50s)     # prepare test table
  ✓ Step 2 completed (4.85s)     # prepare model for prediction
  ✓ Step 3 completed (31.87s)    # submit prediction job and stream logs
  ✓ Step 4 completed (9.40s)     # load results into the logic engine
=== GNN Prediction Complete (51.62s) ===

=== Smoker predictions (sample) ===
Id  predicted_label     prob  actual_smoking
 1                1 0.645295               1
16                0 0.351588               0
21                0 0.178555               0
24                0 0.352124               0
29                1 0.855304               1
35                1 0.836192               0
49                1 0.576184               1
75                0 0.045360               0
92                1 0.707472               1
97                1 0.851055               1

=== Test-set metrics (n=3899) ===
  Test-set ROC-AUC:   0.8485
  Test-set accuracy:  0.7671
  Actual class dist:    {0: 0.6327, 1: 0.3673}
  Predicted class dist: {0: 0.6163, 1: 0.3837}

============================================================
Local run complete.
============================================================
```

### Adapting to your own Snowflake data

`smoker_status_prediction.py` shows the same pipeline against Snowflake-hosted tables. The script's defaults expect five tables -- `PEOPLE`, `RELATED`, `TRAIN`, `VALIDATION`, `TEST` -- inside `SMOKER_STATUS_PREDICTION.DATA`. To adapt:

1. **Create the database and `DATA` schema, and define the five tables.** Run this in a Snowflake SQL worksheet. Column names are quoted so spaces and parentheses in feature names (`height(cm)`, `fasting blood sugar`, ...) are preserved as-is.
   ```sql
   SET db_name     = 'SMOKER_STATUS_PREDICTION';
   SET schema_data = 'SMOKER_STATUS_PREDICTION.DATA';

   CREATE DATABASE IF NOT EXISTS identifier($db_name);
   CREATE SCHEMA   IF NOT EXISTS identifier($schema_data);

   USE SCHEMA identifier($schema_data);

   CREATE OR REPLACE TABLE PEOPLE (
       "Id"                  NUMBER,
       "age"                 NUMBER,
       "height(cm)"          NUMBER,
       "weight(kg)"          NUMBER,
       "systolic"            NUMBER,
       "relaxation"          NUMBER,
       "fasting blood sugar" NUMBER,
       "Cholesterol"         NUMBER,
       "triglyceride"        NUMBER,
       "HDL"                 NUMBER,
       "LDL"                 NUMBER,
       "hemoglobin"          FLOAT,
       "Urine protein"       NUMBER,
       "serum creatinine"    FLOAT,
       "AST"                 NUMBER,
       "ALT"                 NUMBER,
       "Gtp"                 NUMBER,
       "dental caries"       NUMBER
   );

   CREATE OR REPLACE TABLE RELATED    ("person1" NUMBER, "person2" NUMBER);
   CREATE OR REPLACE TABLE TRAIN      ("Id" NUMBER, "smoking" NUMBER);
   CREATE OR REPLACE TABLE VALIDATION ("Id" NUMBER, "smoking" NUMBER);
   CREATE OR REPLACE TABLE TEST       ("Id" NUMBER, "smoking" NUMBER);
   ```

2. **Load the bundled CSVs into the five tables.** Two ways:

   - **Snowsight UI**: For each table, open the table page and click *Load Data* -> upload the matching CSV from `data/`. The wizard auto-detects headers; confirm that each column maps to the quoted name created above.
   - **SnowSQL / Snowflake CLI** (reproducible): Stage each CSV via `PUT` and load with `COPY INTO`. Run from a shell pointing at the template's `data/` directory:
     ```sql
     CREATE OR REPLACE FILE FORMAT csv_with_header
         TYPE = CSV FIELD_DELIMITER = ',' SKIP_HEADER = 1
         FIELD_OPTIONALLY_ENCLOSED_BY = '"';

     PUT file://data/people.csv     @%PEOPLE     AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
     PUT file://data/related.csv    @%RELATED    AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
     PUT file://data/train.csv      @%TRAIN      AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
     PUT file://data/validation.csv @%VALIDATION AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
     PUT file://data/test.csv       @%TEST       AUTO_COMPRESS=FALSE OVERWRITE=TRUE;

     COPY INTO PEOPLE     FROM @%PEOPLE     FILE_FORMAT = csv_with_header;
     COPY INTO RELATED    FROM @%RELATED    FILE_FORMAT = csv_with_header;
     COPY INTO TRAIN      FROM @%TRAIN      FILE_FORMAT = csv_with_header;
     COPY INTO VALIDATION FROM @%VALIDATION FILE_FORMAT = csv_with_header;
     COPY INTO TEST       FROM @%TEST       FILE_FORMAT = csv_with_header;
     ```

3. **Grant the Native App access** to the `EXPERIMENTS` schema for GNN artifacts -- same SQL block as [step 5 of the Quickstart](#quickstart).

4. **Enable change tracking in your `raiconfig.yaml`.** The Snowflake-path script imports tables via `Table(...).to_schema()`, which requires change tracking to be on:
   ```yaml
   data:
     ensure_change_tracking: true
   ```
   Without it, the SDK warns at startup that "GNN workflows using Snowflake tables will fail without it" and the script will not be able to import the source tables. The local CSV path (`smoker_status_prediction_local.py`) does not need this.

5. **Edit the table references** at the top of the script if your database/schema names differ from the defaults:
   ```python
   DATABASE = "YOUR_DB"
   SCHEMA = "YOUR_SCHEMA"           # holds PEOPLE and RELATED
   TASK_SCHEMA = "YOUR_TASK_SCHEMA" # holds TRAIN, VALIDATION, TEST
   GNN_EXP_DATABASE = "YOUR_DB"
   GNN_EXP_SCHEMA = "EXPERIMENTS"
   ```

6. **Run:**
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
    ├── people.csv          # 38,984 rows, 18 columns (Id + 17 features)
    ├── related.csv         # 58,355 (person1, person2) pairs
    ├── train.csv           # 31,187 (Id, smoking) rows
    ├── validation.csv      # 3,898 rows
    └── test.csv            # 3,899 rows
```

**Start here**: run `python smoker_status_prediction_local.py` for the full run end to end (no external setup beyond Snowflake grants), or follow `runbook.md` to reproduce it step by step with the RAI skills. Use `smoker_status_prediction.py` as the adaptation reference when you wire this pattern into your own Snowflake data.

## Sample data

> [!IMPORTANT]
> The bundled CSVs are a **demo dataset** for showing the GNN methodology end-to-end. The medical / demographic columns come from a publicly-available smoking-status dataset; the `RELATED` edges are **synthetically constructed** (see below). Predictions are **illustrative, not clinically meaningful** — don't treat them as a medical signal.

The dataset contains medical and demographic attributes for a population of individuals in the `PEOPLE` table, along with a `RELATED` table of connected pairs. Connections were constructed so that linked individuals are more likely to share the same smoking status, giving the network a genuinely informative signal for the GNN.

- **people.csv** -- an `Id` identifier plus 17 medical/demographic features: 16 continuous (`age`, `height(cm)`, `weight(kg)`, blood pressure (`systolic`, `relaxation`), `fasting blood sugar`, lipids (`Cholesterol`, `triglyceride`, `HDL`, `LDL`), `hemoglobin`, urinalysis (`Urine protein`, `serum creatinine`), liver enzymes (`AST`, `ALT`, `Gtp`)) plus a binary `dental caries` category.
- **related.csv** -- pairs of `Id`s representing connections between persons.
- **train / validation / test** -- split-specific `(Id, smoking)` rows where `smoking ∈ {0, 1}`.

## Model overview

- **Key entities**: `People` (individuals with demographic and medical attributes), `Related` (pairs of people, used as the edge list of the graph neural network (GNN) graph), and the split tables `TrainTable` / `ValidationTable` / `TestTable`.
- **Primary identifiers**: `People.Id` (integer, unique per person). `Related`, `TrainTable`, `ValidationTable`, and `TestTable` have no key of their own — they join back to `People` by `Id`.
- **Important invariants**: `Id` values in `Related` and the split tables must reference an existing `People.Id`; the `smoking` label is binary (`0` / `1`); `TestTable.smoking` is held out and never fed to the model; the three splits partition the labeled population (31,187 train / 3,898 validation / 3,899 test).

### Pipeline stages

```text
People + Related (CSVs or Snowflake tables)
  → Build the graph: nodes as persons, self-referential edges People ↔ People (via Related)
  → Configure features: PropertyTransformer (continuous medical features + dental_caries category)
  → Define the task: Train / Validation / Test relationships
  → Train and predict: binary-classification GNN → predictions on the Test cohort
  → (Optional) Register and load the trained model
```

For the full concept and property definitions, see `smoker_status_prediction_local.py` (and `smoker_status_prediction.py` for the Snowflake pipeline); `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline turns the `PEOPLE` table into graph nodes and the `RELATED` pairs into edges, configures the medical/demographic features, defines the train/validation/test task, then trains a binary-classification GNN and predicts smoking status on the held-out test cohort (see the *Pipeline stages* diagram above).

1. **Build the graph.** Each `RELATED` row becomes a directed edge from one `People` node to another. Because both endpoints are the same concept, the destination endpoint uses a `.ref()` of `People`.
2. **Configure features.** A `PropertyTransformer` lists the medical and demographic columns as continuous features, treats the binary `dental caries` indicator as a category, and drops `Id` so the identifier isn't fed into the model. Column names with spaces or parentheses (`height(cm)`, `fasting blood sugar`) are accessed via `getattr`, and the schema is preserved as-is so the same names work against the underlying Snowflake tables.
3. **Define the task.** A node-classification task pairs each labeled `People` row with its smoking status via train and validation relationships; the test relationship omits the label because it is held out.
4. **Train and predict.** The GNN is instantiated with the graph, the transformer, and the train/validation relationships, fit, then used to attach predictions over the held-out test cohort back onto each `People` node.
5. **(Optional) Register and load.** The bottom of each script has a commented-out block that registers the trained model in the Snowflake Model Registry and loads it back into a fresh `GNN` instance to predict without retraining.

See `smoker_status_prediction_local.py` / `smoker_status_prediction.py` for the implementation and `runbook.md` for the skill-driven reproduction.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own equivalent files (people, edges, splits). Column names need to match the `PropertyTransformer`, or you'll need to edit the transformer.
- For Snowflake adaptation, edit the `DATABASE`, `SCHEMA`, `TASK_SCHEMA`, and `GNN_EXP_*` constants at the top of `smoker_status_prediction.py`.

### Tune parameters

- `n_epochs` -- increase for better convergence on a larger dataset.
- `lr` -- lower if training loss bounces.
- `eval_metric` -- switch to `"accuracy"` or `"f1"` if those metrics suit your problem better.
- `device` -- use `"cuda"` for faster training on a GPU-enabled engine.

For the full hyperparameter list, see the [Configure a GNN](https://docs.relational.ai/build/guides/reasoning/predictive/configure-a-GNN) guide.

### Extend the model

- **Add categorical demographics** (e.g. occupation, income bracket): list them under `category=[...]` in the `PropertyTransformer`.
- **Try a multiclass task**: if your label has more than two values (e.g. never / light / heavy smoker), change `task_type="multiclass_classification"` and use `eval_metric="macro_f1"` or `"accuracy"`.
- **Register the model** for reuse: uncomment the bonus section at the bottom of either script.

### Scale up / productionize

- Move from the bundled CSVs to Snowflake-hosted tables with `smoker_status_prediction.py` (see *Adapting to your own Snowflake data* under Quickstart); the graph, features, and task setup are unchanged.
- Train on a GPU-enabled engine (`device="cuda"`) for larger populations; CPU is fine for the bundled ~39K-person demo.
- Pin `relationalai` (see Prerequisites) so runs stay reproducible across environments.
- Register the trained model in the Snowflake Model Registry (the optional block at the bottom of each script) so downstream jobs load and predict without retraining.

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

CREATE DATABASE IF NOT EXISTS identifier($db_name);
CREATE SCHEMA   IF NOT EXISTS identifier($schema_experiments);

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

## Learn more

### Core concepts

- [Predictive reasoning (GNN)](https://docs.relational.ai/) — graph neural network modeling on an ontology: nodes, edges, and features.
- [PyRel v1 query language](https://docs.relational.ai/) — `model.define(...)` / `model.where(...)`, used to build the edge list and split relationships.

### Reasoner reference

- [Configure a GNN](https://docs.relational.ai/build/guides/reasoning/predictive/configure-a-GNN) — the full hyperparameter list for `GNN(...)`.
- [PropertyTransformer](https://docs.relational.ai/) — declaring continuous vs. category features and dropping identifier columns.
- [Model Registry](https://docs.relational.ai/) — registering, loading, and reusing a trained model without retraining (the optional bonus block).

## Support

- File issues at the RelationalAI templates repository.
