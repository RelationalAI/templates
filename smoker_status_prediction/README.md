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
- A registered, versioned model in the template's public schema, which the deployed model predicts with.

## What's included

- **Model**: `model/` -- the deployed model: concepts and splits (`schema.py`, `source.py`), the graph, the feature types, and the GNN with its predictions (`reasoning.py`)
- **Training**: `train.py` -- trains the GNN over the deployed splits and registers its version
- **Query**: `queries/smoker_report.py` -- prints the data summary, a sample of predictions, and the test-set metrics from the deployed model
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the code itself.
- **Sample data** (`data/`) -- bundled demo dataset for end-to-end runs; predictions are illustrative of the GNN methodology, not clinically meaningful (see [Sample data](#sample-data) for what's real vs. constructed):
  - `people.csv` -- 38,984 individuals with demographic and medical features.
  - `related.csv` -- 58,355 connection pairs between people.
  - `train.csv` / `validation.csv` / `test.csv` -- labeled splits with smoking status.

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A role that can deploy models, set up once by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) (**Try it out**, or **Governed setup** for a shared account). This template has no prescriptive solve, so it needs no PAT setup.
- A Snowflake user that holds that role.

The bundled CSVs in `data/` ship with the template; running it needs no source tables. To read your own Snowflake tables instead, see [Adapting to your own Snowflake data](#adapting-to-your-own-snowflake-data). The GNN trains on the predictive reasoner and stores its experiments and registered versions in the template's public schema.

### Tools

- Python >= 3.10
- The `relationalai[gnn]` SDK and the `rai` CLI (installed by the Quickstart's `python -m pip install .`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, a role that can deploy models, and a Snowflake user that holds it.

Before the first deploy, create this template's two schemas as the model role, and have an administrator grant the RAI Native App access to them. The GNN keeps its experiments and registered versions in the public schema, and the internal schema holds only this model's objects, so the grants cover all of it:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.SMOKER_STATUS_PREDICTION;
CREATE SCHEMA IF NOT EXISTS <DB>.SMOKER_STATUS_PREDICTION_META;

-- as an administrator
GRANT USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT USAGE ON SCHEMA <DB>.SMOKER_STATUS_PREDICTION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE EXPERIMENT ON SCHEMA <DB>.SMOKER_STATUS_PREDICTION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE MODEL ON SCHEMA <DB>.SMOKER_STATUS_PREDICTION TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.SMOKER_STATUS_PREDICTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.SMOKER_STATUS_PREDICTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.SMOKER_STATUS_PREDICTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.SMOKER_STATUS_PREDICTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.SMOKER_STATUS_PREDICTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.SMOKER_STATUS_PREDICTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.SMOKER_STATUS_PREDICTION_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model, train the GNN, and query its predictions:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/smoker_status_prediction.zip), unzip it, and enter the template directory:

   ```bash
   unzip smoker_status_prediction.zip
   cd smoker_status_prediction
   ```

2. **Create a Python environment**

   Create and activate a virtual environment, then update pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

3. **Install the template**

   Install the dependencies pinned in `pyproject.toml`:

   ```bash
   python -m pip install .
   ```

4. **Configure your project**

   Use the configuration builder in [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/#configure-your-project) to create `raiconfig.yaml` in the template directory and verify your connection.

   Set the connection `role` to the model role, then add the predictive reasoner, the registered version the GNN predicts with, and a `deployment` section. Give each template its own schema pair so two deployed templates never share one:

   ```yaml
   reasoners:
     predictive:
       name: smoker_status_prediction_gnn     # created on first use if it doesn't exist
       gnns:
         smoker_status:                 # the GNN's name in model/reasoning.py
           registry: <DB>.SMOKER_STATUS_PREDICTION
           model: SMOKER_STATUS
           version: V1                  # train.py registers this version
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.SMOKER_STATUS_PREDICTION
     identity:
       internal_schema: <DB>.SMOKER_STATUS_PREDICTION_META
     schedules:
       standard:
         interval_s: 0                  # refresh only on deploy or on demand
     schedule: standard
   ```

5. **Deploy the model**

   Deploy the model in `model/` to the schemas in `raiconfig.yaml`:

   ```bash
   rai models deploy --path model
   ```

   The deploy waits for the model's first refresh, which loads the people, their connections, and the train, validation, and test splits. No version of the GNN is registered yet, so this refresh makes no predictions.

   Deploying again without changing the model applies no updates and does not refresh.

6. **Train the GNN**

   Train the GNN over the deployed splits and register it as the version named in `raiconfig.yaml`:

   ```bash
   python train.py
   ```

   Then refresh the deployed model so it predicts with this version: `CALL DB.SMOKER_STATUS_PREDICTION_META._INTERNAL_REFRESH_MODEL('standard', NULL);` with your database in place of `DB`. The registry refuses to overwrite a version, so to retrain, set a new `version` in `raiconfig.yaml` first.

7. **Query the results**

   Print the predictions from the deployed model:

   ```bash
   python -m queries.smoker_report
   ```

   ```text
   People: 38,984  Related: 58,355
   Splits: train=31,187  val=3,898  test=3,899

   === Smoker predictions (sample) ===
    Id  predicted_label     prob  actual_smoking
     1                1 0.716425               1
    16                0 0.319361               0
    21                0 0.205867               0
    24                0 0.322035               0
    29                1 0.856083               1
    35                1 0.851715               0
    49                1 0.571429               1
    75                0 0.049680               0
    92                1 0.706254               1
    97                1 0.854486               1

   === Test-set metrics (n=3899) ===
     Test-set ROC-AUC:   0.8479
     Test-set accuracy:  0.7630
     Actual class dist:    {0: 0.6327, 1: 0.3673}
     Predicted class dist: {0: 0.6055, 1: 0.3945}
   ```

   The sample shows the first 10 test people by Id. Predicted probabilities and the metrics vary a little from one training run to the next, and the predicted class distribution with them; the data summary and the actual labels do not. See `runbook.md` for the step-by-step walkthrough.

   To predict again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.SMOKER_STATUS_PREDICTION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
   ```

8. **Tear down the deployment**

   Preview what the teardown removes, then remove it:

   ```bash
   rai models teardown
   rai models teardown --force
   ```

   The teardown removes the deployed objects and keeps the two schemas, with the GNN's experiments and registered versions in the public schema.

## Template structure

```text
.
├── README.md                       # this file
├── pyproject.toml                  # dependencies
├── model/
│   ├── __init__.py                 # exports for train.py and the query
│   ├── schema.py                   # concepts and the Train/Validation/Test task relationships
│   ├── source.py                   # bundled CSVs bound to the schema
│   └── reasoning.py                # graph, feature types, the GNN and its predictions
├── train.py                        # trains the GNN and registers its version
├── queries/
│   └── smoker_report.py            # data summary, prediction sample, and test-set metrics
└── data/
    ├── people.csv          # 38,984 rows, 18 columns (Id + 17 features)
    ├── related.csv         # 58,355 (person1, person2) pairs
    ├── train.csv           # 31,187 (Id, smoking) rows
    ├── validation.csv      # 3,898 rows
    └── test.csv            # 3,899 rows
```

**Start here**: follow the [Quickstart](#quickstart) to deploy the model, train the GNN, and print the predictions, or follow `runbook.md` to reproduce it step by step with the RAI skills. To read your own Snowflake tables, see [Adapting to your own Snowflake data](#adapting-to-your-own-snowflake-data).

## Sample data

> [!IMPORTANT]
> The bundled CSVs are a **demo dataset** for showing the GNN methodology end-to-end. The medical / demographic columns come from a publicly-available smoking-status dataset; the `RELATED` edges are **synthetically constructed** (see below). Predictions are **illustrative, not clinically meaningful** — don't treat them as a medical signal.

The dataset contains medical and demographic attributes for a population of individuals in the `PEOPLE` table, along with a `RELATED` table of connected pairs. Connections were constructed so that linked individuals are more likely to share the same smoking status, giving the network a genuinely informative signal for the GNN.

- **people.csv** -- an `Id` identifier plus 17 medical/demographic features: 16 continuous (`age`, `height(cm)`, `weight(kg)`, blood pressure (`systolic`, `relaxation`), `fasting blood sugar`, lipids (`Cholesterol`, `triglyceride`, `HDL`, `LDL`), `hemoglobin`, urinalysis (`Urine protein`, `serum creatinine`), liver enzymes (`AST`, `ALT`, `Gtp`)) plus a binary `dental caries` category.
- **related.csv** -- pairs of `Id`s representing connections between persons.
- **train / validation / test** -- split-specific `(Id, smoking)` rows where `smoking ∈ {0, 1}`.

`model/source.py` renames the `people.csv` headers that contain spaces or parentheses as it loads them (`height(cm)` becomes `height_cm`, `fasting blood sugar` becomes `fasting_blood_sugar`, and so on, all lowercase); the files themselves are unchanged.

## Model overview

- **Key entities**: `People` (individuals with demographic and medical attributes), `Related` (pairs of people, used as the edge list of the graph neural network (GNN) graph), and the split tables `TrainTable` / `ValidationTable` / `TestTable`.
- **Primary identifiers**: `People.Id` (integer, unique per person). `Related`, `TrainTable`, `ValidationTable`, and `TestTable` have no key of their own — they join back to `People` by `Id`.
- **Important invariants**: `Id` values in `Related` and the split tables must reference an existing `People.Id`; the `smoking` label is binary (`0` / `1`); `TestTable.smoking` is held out and never fed to the model; the three splits partition the labeled population (31,187 train / 3,898 validation / 3,899 test).

### Pipeline stages

```text
People + Related (bundled CSVs)
  → Build the graph: nodes as persons, self-referential edges People ↔ People (via Related)
  → Configure features: PropertyTransformer (continuous medical features + dental_caries category)
  → Define the task: Train / Validation / Test relationships
  → Train: binary-classification GNN, registered as a model version
  → Predict: every refresh scores the Test cohort with that version
```

For the full concept and property definitions, see `model/`; `runbook.md` builds them step by step with the RAI skills.

## How it works

The pipeline turns the `PEOPLE` table into graph nodes and the `RELATED` pairs into edges, configures the medical/demographic features, defines the train/validation/test task, then trains a binary-classification GNN and predicts smoking status on the held-out test cohort (see the *Pipeline stages* diagram above).

1. **Build the graph.** Each `RELATED` row becomes a directed edge from one `People` node to another. Because both endpoints are the same concept, the destination endpoint uses a `.ref()` of `People`.
2. **Configure features.** A `PropertyTransformer` lists the medical and demographic columns as continuous features, treats the binary `dental caries` indicator as a category, and drops `Id` so the identifier isn't fed into the model. `model/source.py` renames the CSV headers that contain spaces or parentheses (`height(cm)`, `fasting blood sugar`) to identifier-safe names (`height_cm`, `fasting_blood_sugar`) as it loads them, so the transformer refers to each feature as a plain property.
3. **Define the task.** A node-classification task pairs each labeled `People` row with its smoking status via train and validation relationships; the test relationship omits the label because it is held out.
4. **Train and predict.** The GNN is instantiated with the graph, the transformer, and the train/validation relationships, fit, then used to attach predictions over the held-out test cohort back onto each `People` node.
5. **Register and predict.** `train.py` registers the trained run as a version in the Snowflake Model Registry, and every refresh of the deployed model scores the test cohort with that version, so predictions need no retraining.

See `model/reasoning.py` for the graph and the GNN, `queries/smoker_report.py` for the metrics, and `runbook.md` for the skill-driven reproduction.

## Customize this template

### Use your own data

- Replace the CSVs in `data/` with your own equivalent files (people, edges, splits). Column names need to match the `PropertyTransformer`, or you'll need to edit the transformer.
- To read Snowflake tables instead, see [Adapting to your own Snowflake data](#adapting-to-your-own-snowflake-data).

### Tune parameters

- `n_epochs` -- increase for better convergence on a larger dataset.
- `lr` -- lower if training loss bounces.
- `eval_metric` -- switch to `"accuracy"` or `"f1"` if those metrics suit your problem better.
- Predictive reasoner size -- set `reasoners.predictive.size` in `raiconfig.yaml` to a GPU size for faster training: a deployed GNN runs on the device that size provides.

For the full hyperparameter list, see the [Configure a GNN](https://docs.relational.ai/build/guides/reasoning/predictive/configure-a-GNN) guide.

### Extend the model

- **Add categorical demographics** (e.g. occupation, income bracket): list them under `category=[...]` in the `PropertyTransformer`.
- **Try a multiclass task**: if your label has more than two values (e.g. never / light / heavy smoker), change `task_type="multiclass_classification"` and use `eval_metric="macro_f1"` or `"accuracy"`.
- **Train a new version**: the registry refuses to overwrite a version, so set a new `version` under `reasoners.predictive.gnns.smoker_status` in `raiconfig.yaml`, then run `python train.py` and the refresh call again.

### Scale up / productionize

- Move from the bundled CSVs to Snowflake-hosted tables (see [Adapting to your own Snowflake data](#adapting-to-your-own-snowflake-data)); the graph, features, and task setup are unchanged.
- Train on a GPU predictive reasoner size for larger populations; the default size is fine for the bundled ~39K-person demo.
- Pin `relationalai` (see Prerequisites) so runs stay reproducible across environments.

### Adapting to your own Snowflake data

To read Snowflake tables instead of the bundled CSVs, replace the `read_csv` and `model.data(...)` definitions in `model/source.py` with table references, name the schema that holds the tables in `raiconfig.yaml`, then redeploy and train a new version:

```python
Table = model.Table
model.define(People.new(Table("PEOPLE").to_schema()))
model.define(Related.new(Table("RELATED").to_schema()))
model.define(TrainTable.new(Table("TRAIN").to_schema()))
model.define(ValidationTable.new(Table("VALIDATION").to_schema()))
model.define(TestTable.new(Table("TEST").to_schema()))
```

```yaml
tables:
  default_schema: MY_DB.MY_SCHEMA   # resolves the unqualified table names above
```

The tables carry the same columns as the CSVs, created with quoted names so Snowflake keeps their case and matching the names the model uses: `PEOPLE` with `"Id"` and the lowercase feature names that `model/reasoning.py` reads (`"height_cm"`, `"fasting_blood_sugar"`, ...), `RELATED` with `"person1"` and `"person2"`, and `TRAIN`, `VALIDATION`, and `TEST` with `"Id"` and `"smoking"`.

## Troubleshooting

<details>
<summary>Predictions are all the same class</summary>

Check the class balance in `train.csv` -- if it's heavily skewed, consider re-sampling or training for more epochs with a lower learning rate. Also verify that the `RELATED` edges correlate with shared smoking status; without an informative network, the GNN reduces to a tabular model.
</details>

<details>
<summary>GNN training is very slow</summary>

A deployed GNN trains on the predictive reasoner named in `raiconfig.yaml`, on the device its size provides. If training is slow, set `reasoners.predictive.size` to a GPU size.
</details>

<details>
<summary><code>Experiment tracking database ... does not exist or is not accessible</code> when training</summary>

The GNN keeps its experiments and registered versions in the public schema named in `raiconfig.yaml`, and the RAI Native App needs USAGE on its database and schema plus CREATE EXPERIMENT and CREATE MODEL on the schema. Run the setup grants from the [Quickstart](#quickstart) as an administrator, then run `python train.py` again.
</details>

<details>
<summary>The report prints <code>(no test-set predictions returned)</code></summary>

The deployed model has not refreshed since a version was registered: the refresh that `rai models deploy` waits for runs before `python train.py`. Run `python train.py` if you haven't, then the refresh call from step 6 of the Quickstart, and query again.
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
- [Model Registry](https://docs.relational.ai/) — registering, loading, and reusing a trained model without retraining.

## Support

- File issues at the RelationalAI templates repository.
