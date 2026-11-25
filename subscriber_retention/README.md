---
title: "Subscriber Retention"
description: "Score every telco subscriber for churn risk using a graph neural network (GNN) that learns from both plan attributes and each subscriber's position in the call network, then surface the highest-risk subscribers per segment for retention campaigns."
featured: false
experience_level: advanced
industry: "Technology & Telecom"
reasoning_types:
  - Graph
  - Predictive
tags:
  - Graph Neural Network (GNN)
  - Regression
  - Churn Prediction
  - Graph Features
  - Telco
  - Multi-Reasoner
---

## What this template is for

Telco retention teams need to know which subscribers are most likely to churn, so they can spend a limited campaign budget on the people most worth keeping. Traditional churn models lean on plan attributes and demographics alone, and miss a signal the operator already owns: the call network. A subscriber who talks to many others, or sits at the center of a tight calling community, behaves differently from an isolated one -- and that structure predicts retention.

This template scores the held-out test subscribers for churn risk using both their plan attributes and their standing in the call network, then ranks the highest-risk subscribers within each segment so a retention team can act on them first.

**A graph neural network learns per-subscriber churn risk from plan and demographic attributes enriched with call-network features**, so who a subscriber talks to shapes the score, not just what plan they hold.

## Who this is for

- Telco data scientists building churn-risk scoring pipelines that combine static plan attributes with relational/network signal
- Retention marketers who need a per-subscriber risk score by segment to drive targeted offer campaigns
- ML engineers exploring graph neural network (GNN) regression over customer graphs
- Teams already querying RelationalAI on a Subscriber/Plan/Call ontology who want to layer a predictive head onto it

**Assumed knowledge**: comfortable with Python, basic ML concepts (regression, root-mean-square error / RMSE), and graph data structures. The telco, graph, and GNN terms are explained as they come up.

## What you'll build

- A per-subscriber churn-risk score, predicted by a **graph neural network (GNN) regression head** (the predictive reasoner) from plan attributes, demographics, and call-network features.
- Call-network features enriched onto each subscriber by the **graph reasoner** -- a PageRank "social influence" score plus aggregate-derived `outgoing_calls` / `incoming_calls` counts -- so the GNN sees who each subscriber talks to.
- A retention-ready report of the top-N highest-predicted-risk subscribers per segment: the deployed model publishes each test subscriber's predicted risk and its rank within its segment, and the report prints the first N of each segment.
- A pipeline that runs end-to-end on the small bundled telco dataset (~1,200 subscribers, ~6,000 calls) with no Snowflake source-data setup and no GPU.

Built using the **graph reasoner** (PageRank on the call graph) and the **predictive reasoner** (GNN regression scored per subscriber).

## What's included

- **Model**: `model/` — the deployed model: concepts, data and splits (`schema.py`, `source.py`), the call graph and call features (`call_signals.py`), the GNN and its published predictions (`churn_predictor.py`), and the counts, score range, per-segment ranks and RMSE the report prints (`data_profile.py`, `prediction_summary.py`)
- **Training**: `train.py` — trains the GNN over the deployed splits and registers its version
- **Query**: `queries/churn_report.py` — prints the top-N highest-predicted-risk subscribers per segment from the deployed model
- **Runbook**: `runbook.md` — a paste-testable walkthrough that reproduces the template step by step with the RAI skills; as important a reference as the code itself.
- **Ontology**: `Subscriber` (with denormalized plan attributes), `Call` (edge-intermediary for the call graph), and three task-table concepts: `TrainTable` and `ValTable` carry the churn-risk labels, and `TestTable` lists the subscribers to score; `ChurnRiskPrediction` publishes each scored subscriber's predicted risk
- **Sample data**: small telco subset (subscribers + plans + call detail records); see [Sample data](#sample-data) below
- **Outputs**: subscriber/call counts, churn-risk distribution, GNN training job status, up to 5 highest-risk test subscribers per segment, test-set RMSE

## Prerequisites

### Access

- A Snowflake account that has the RAI Native App installed.
- A role that can deploy models, set up once by an account administrator: follow [Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup) (**Try it out**, or **Governed setup** for a shared account). This template has no prescriptive solve, so it needs no PAT setup.
- A Snowflake user that holds that role.

The bundled CSVs ship with the template; there is no source-table setup. The GNN trains on the predictive reasoner and stores its experiments and registered versions in the template's public schema.

### Tools

- Python 3.10 through 3.14 (the range relationalai 2.3.0 supports)
- The `relationalai[gnn]` SDK and the `rai` CLI (installed by the Quickstart's `python -m pip install .`).

## Quickstart

Before you start, install Python 3.10 or later and complete the access prerequisites above: a Snowflake account with the RAI Native App, a role that can deploy models, and a Snowflake user that holds it.

Before the first deploy, create this template's two schemas as the model role, and have an administrator grant the RAI Native App access to them. The GNN keeps its experiments and registered versions in the public schema, and the internal schema holds only this model's objects, so the grants cover all of it:

```sql
-- as the model role
CREATE SCHEMA IF NOT EXISTS <DB>.SUBSCRIBER_RETENTION;
CREATE SCHEMA IF NOT EXISTS <DB>.SUBSCRIBER_RETENTION_META;

-- as an administrator
GRANT USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT USAGE ON SCHEMA <DB>.SUBSCRIBER_RETENTION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE EXPERIMENT ON SCHEMA <DB>.SUBSCRIBER_RETENTION TO APPLICATION <RAI_APP_NAME>;
GRANT CREATE MODEL ON SCHEMA <DB>.SUBSCRIBER_RETENTION TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON DATABASE <DB> TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON SCHEMA <DB>.SUBSCRIBER_RETENTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER USAGE ON WAREHOUSE <WAREHOUSE> TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL TABLES IN SCHEMA <DB>.SUBSCRIBER_RETENTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL DYNAMIC TABLES IN SCHEMA <DB>.SUBSCRIBER_RETENTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER SELECT ON ALL VIEWS IN SCHEMA <DB>.SUBSCRIBER_RETENTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER INSERT, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA <DB>.SUBSCRIBER_RETENTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT CALLER CREATE TABLE, CREATE STAGE ON SCHEMA <DB>.SUBSCRIBER_RETENTION_META TO APPLICATION <RAI_APP_NAME>;
GRANT INHERITED CALLER READ, WRITE ON ALL STAGES IN SCHEMA <DB>.SUBSCRIBER_RETENTION_META TO APPLICATION <RAI_APP_NAME>;
```

Use this sequence to deploy the model, train the GNN, and query the churn report:

1. **Download the template**

   [Download the ZIP](https://docs.relational.ai/templates/zips/v1/subscriber_retention.zip), unzip it, and enter the template directory:

   ```bash
   unzip subscriber_retention.zip
   cd subscriber_retention
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
       name: subscriber_retention_gnn     # created on first use if it doesn't exist
       gnns:
         churn_risk:                    # the GNN's name in model/churn_predictor.py
           registry: <DB>.SUBSCRIBER_RETENTION
           model: CHURN_RISK
           version: V1                  # train.py registers this version
   deployment:
     role: <MODEL_ROLE>
     public_schema: <DB>.SUBSCRIBER_RETENTION
     identity:
       internal_schema: <DB>.SUBSCRIBER_RETENTION_META
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

   The deploy waits for the model's first refresh, which loads the subscriber and call data with the train, validation, and test splits (drawn in Python from the CSVs when the model package is imported) and computes PageRank on the call graph. No version of the GNN is registered yet, so this refresh makes no predictions.

   Deploying again without changing the model applies no updates and does not refresh.

6. **Train the GNN**

   Train the GNN over the deployed splits and register it as the version named in `raiconfig.yaml`:

   ```bash
   python train.py
   ```

   Then refresh the deployed model so it predicts with this version: `CALL <DB>.SUBSCRIBER_RETENTION_META._INTERNAL_REFRESH_MODEL('standard', NULL);` with your database in place of `<DB>`. The registry refuses to overwrite a version, so to retrain, set a new `version` in `raiconfig.yaml` first.

7. **Query the results**

   Print the churn report from the deployed model:

   ```bash
   python -m queries.churn_report
   ```

   ```text
   Subscribers: 1200  Calls: 6000
   Splits: train=837  val=179  test=184  (stratified by SEGMENT)
   CHURN_RISK_SCORE: min=0.05  mean=0.24  max=0.89

   ============================================================
   Top 5 highest-predicted-risk subscribers per segment
   ============================================================

   [BUDGET]  (55 test subscribers)
          sub_id segment     type  lifetime_value  actual_risk  predicted_risk
   SUB-CON-00314  BUDGET CONSUMER         4173.54         0.07        0.228540
   SUB-CON-00013  BUDGET CONSUMER         4887.25         0.27        0.228511
   SUB-CON-00531  BUDGET CONSUMER         4142.37         0.15        0.228417
   SUB-CON-00881  BUDGET CONSUMER          777.72         0.22        0.228387
   SUB-CON-00769  BUDGET CONSUMER          286.75         0.16        0.228376

   [ENTERPRISE_PREMIUM]  (8 test subscribers)
         sub_id            segment       type  lifetime_value  actual_risk  predicted_risk
   SUB-ENT-0025 ENTERPRISE_PREMIUM ENTERPRISE       464629.41         0.17        0.248166
   SUB-ENT-0013 ENTERPRISE_PREMIUM ENTERPRISE       475433.81         0.72        0.228717
   SUB-ENT-0010 ENTERPRISE_PREMIUM ENTERPRISE        90371.80         0.74        0.228588
   SUB-ENT-0024 ENTERPRISE_PREMIUM ENTERPRISE       149684.34         0.10        0.228553
   SUB-ENT-0045 ENTERPRISE_PREMIUM ENTERPRISE       161219.10         0.19        0.228537

   ...

   Test-set RMSE: 0.1399
   ```

   The report is trimmed here: it prints up to five test subscribers for each of the five segments (the smallest segment has only three). On this small synthetic dataset the GNN converges close to the segment-mean risk (~0.24): there isn't enough learnable signal in 837 training rows of synthetic plan and call data to spread the predictions further. The template demonstrates the pipeline shape, not score quality; pointed at real telco data with stronger churn-correlated features (tenure, billing-event history, support-ticket patterns), the same pipeline produces discriminative per-subscriber scores. Predicted scores and the RMSE vary a little from one training run to the next; the data summary and actual scores do not. See `runbook.md` for the step-by-step walkthrough.

   To predict again without changing the model, refresh the deployed model, then run the query again:

   ```sql
   CALL <DB>.SUBSCRIBER_RETENTION_META._INTERNAL_REFRESH_MODEL('standard', NULL);
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
│   ├── schema.py                   # concepts and the Train/Val/Test task relationships
│   ├── source.py                   # bundled CSVs, plan attributes, and the stratified split
│   ├── call_signals.py             # call graph, PageRank, call-volume features
│   ├── churn_predictor.py          # the GNN and the published predicted risk
│   ├── data_profile.py             # subscriber, call, and split counts; churn-risk score range
│   └── prediction_summary.py       # rank within segment, scored subscribers per segment, RMSE
├── train.py                        # trains the GNN and registers its version
├── queries/
│   └── churn_report.py             # top-N highest-predicted-risk subscribers per segment
└── data/
    └── telco_mini/
        ├── subscribers.csv         # ~1,200 subscribers with demographics + risk scores
        ├── plans_contracts.csv     # one row per active contract, joined onto Subscriber
        ├── call_detail_records.csv # ~6,000 caller→callee call records
        └── billing_events.csv      # billing-cycle records (not used by the default pipeline; available for customization)
```

**Start here**: follow the [Quickstart](#quickstart) to deploy the model, train the GNN, and print the churn report, or follow `runbook.md` to reproduce it step by step with the RAI skills.

## Sample data

Two ways to feed this template:

1. **Bundled (light)** — `data/telco_mini/` ships with the template ZIP. ~1,200 subscribers + ~6,000 calls + 1,200 plans. Demo data. The four identifier columns (`FIRST_NAME`, `LAST_NAME`, `EMAIL`, `PHONE`) are dropped at load time as unused features. No external setup. **Quickstart uses this.**
2. **Bring-your-own** — replace the three CSVs the pipeline reads (`subscribers.csv`, `plans_contracts.csv`, `call_detail_records.csv`) under `data/telco_mini/` with your own subscriber / plan / CDR exports (same column names) and redeploy; `billing_events.csv` is optional. There is no widely-known public telco churn dataset that includes a caller-to-callee call graph (the popular [IBM Telco Customer Churn](https://www.kaggle.com/datasets/blastchar/telco-customer-churn) benchmark is tabular only — no calls, no graph), so the GNN graph path requires real CDR data or a synthetic call-graph generator. See [Scale up / productionize](#scale-up--productionize) for loading from Snowflake.

About the bundled mini set:

- **~1,200 subscribers** across five segments: `BUDGET`, `ENTERPRISE_PREMIUM`, `HIGH_VALUE_INFLUENCER`, `PREMIUM`, `STANDARD`
- **~6,000 call records** wired as Subscriber-to-Subscriber edges for the PageRank graph
- **`CHURN_RISK_SCORE` target** is a continuous 0-1 risk score sourced from the analyst-facing risk model in the source schema. Customers adapting this template would replace it with their own labelled churn ground-truth (binary outcome) — the regression scaffold transfers directly to a binary-classification task by switching `task_type` and the target type.

## Model overview

### Key entities

- **Subscriber** (`sub_id`): one customer with denormalized plan attributes (`plan_type`, `monthly_rate_usd`, `data_limit_gb`, `term_months`, `auto_renew`, etc.) plus demographic fields (`segment`, `subscriber_type`, `lifetime_value_usd`, `nps_score`, `signup_date`). Enriched at pipeline time with `pagerank` and `outgoing_calls` / `incoming_calls`.
- **Call**: one call record between two subscribers; serves only as the edge intermediary for the PageRank graph and the call-volume aggregates. Has no identity property — only the edges matter downstream.

**Primary identifiers**: `Subscriber.sub_id` (string, unique per customer). `Call` has no key of its own — its `caller_sub_id` / `callee_sub_id` reference `Subscriber.sub_id` to form call-graph edges.

**Important invariants**: `churn_risk_score` is a fraction in `[0, 1]` (the regression target); every `Call`'s `caller_sub_id` and `callee_sub_id` must resolve to an existing `Subscriber.sub_id`; each subscriber row carries exactly one denormalized plan (1:1 join); `sub_id`, `postal_code`, and the target are dropped from the feature set before training.

For the full concept and property definitions, see `model/`; `runbook.md` builds them step by step with the RAI skills.

### Pipeline stages

```text
Subscribers + Plans + Call records (bundled CSVs, denormalized to Subscriber)
  → Graph:       PageRank on the Subscriber→Subscriber call graph
                 + aggregate-derived outgoing_calls / incoming_calls
  → Predictive:  GNN regression on Subscriber.churn_risk_score (continuous 0-1)
  → Reporting:   top-N highest-predicted-risk subscribers per segment
```

## How it works

**1. Build the call graph.** A directed `Subscriber → Subscriber` graph is built with one edge per caller–callee pair. PageRank runs over it and is bound back to a `Subscriber.pagerank` property, so each subscriber's "social influence" in the call network becomes a continuous feature the GNN can learn from.

**2. Derive call-volume features.** Two count-based rules derive `outgoing_calls` and `incoming_calls` per subscriber via `count(Call).per(Subscriber)` aggregates. These attach to the same `Subscriber` row PageRank is on, so the GNN sees one feature row per subscriber with graph structure and call volume blended in.

**3. Declare features and target.** A `PropertyTransformer` declares each feature's type explicitly — categorical, continuous, integer, datetime — and drops the primary key, high-cardinality `postal_code`, and the `churn_risk_score` target from the feature set.

**4. Train and predict.** The split is stratified by `SEGMENT` so each segment's risk distribution carries through train/val/test. The GNN trains as a regression head evaluated with RMSE, then scores the held-out test subscribers; predictions bind back as `Subscriber.predictions`, and a rule publishes each one on its own `ChurnRiskPrediction` concept for downstream queries.

**5. Top-N per segment.** A rule links each published prediction to its subscriber and ranks it within the subscriber's segment (ties by subscriber ID), and the report prints the first N of each segment: the highest-predicted-risk subscribers a retention team should act on first.

For the implementation, see `model/call_signals.py`, `model/churn_predictor.py`, `model/prediction_summary.py`, and `queries/churn_report.py`; to reproduce it step by step with the RAI skills, follow `runbook.md`.

## Customize this template

### Use your own data

- **Repoint to your own subscriber data** — replace the CSVs under `data/telco_mini/` with your real subscriber/plan/CDR exports (same column names), redeploy, and train a new version.

### Tune parameters

- **Adjust the segment stratification** — the default split in `model/source.py` stratifies by `SEGMENT`. For very imbalanced churn outcomes, stratify by the target instead (or in addition).

### Extend the model

- **Switch to binary churn classification** — change `task_type="regression"` → `"binary_classification"` and set the train/val target to a Boolean churn outcome instead of a continuous risk score. The graph + rules stages stay identical.
- **Add weights to the call graph** — set `weighted=True` on the `Graph(...)` call and add an aggregated edge-weight property (e.g. total call-duration or call-count per pair). The PageRank scores will reflect call intensity, not just topology.
- **Bring more features in** — the bundled `billing_events.csv` is not used by the default pipeline. To wire it in as a billing-driven feature, declare a `BillingEvent` concept in `model/schema.py`, load it in `model/source.py`, derive a `Subscriber.late_payment_count` rule from `PAYMENT_STATUS = "OVERDUE"` in a new `model/billing_signals.py` that `model/churn_predictor.py` imports as it imports `call_signals.py`, then add it to the integer features in `PropertyTransformer`:

  ```python
  billing_df = pd.read_csv(DATA_DIR / "billing_events.csv")
  BillingEvent = Concept("BillingEvent", identify_by={"billing_id": String})
  model.define(BillingEvent.new(model.data(billing_df).to_schema()))

  Subscriber.late_payment_count = model.Property(
      f"{Subscriber} has {Integer:late_payment_count}"
  )
  model.define(
      Subscriber.late_payment_count(count(BillingEvent).per(Subscriber))
  ).where(
      BillingEvent.sub_id == Subscriber.sub_id,
      BillingEvent.payment_status == "OVERDUE",
  )

  # then add Subscriber.late_payment_count to PropertyTransformer(integer=[...])
  ```

### Scale up / productionize

The bundled CSVs are loaded via `model.data(df)` for a no-setup local demo. To run against full data living in Snowflake instead:

1. Replace the three `pd.read_csv(...)` calls in `model/source.py` with Snowpark queries (or use `model.Table("<DB>.<SCHEMA>.<TABLE>")` directly per the `rai-pyrel` skill's data-loading guidance):
   ```python
   from relationalai.config import SnowflakeConnection, create_config
   from snowflake import snowpark
   session: snowpark.Session = create_config().get_session(SnowflakeConnection)

   sub_df = session.sql("SELECT * FROM YOUR_DB.RAW.SUBSCRIBERS").to_pandas()
   plan_df = session.sql("SELECT * FROM YOUR_DB.RAW.PLANS_CONTRACTS").to_pandas()
   calls_df = session.sql("SELECT * FROM YOUR_DB.RAW.CALL_DETAIL_RECORDS").to_pandas()
   ```
2. Drop unused identifier columns the same way (`FIRST_NAME`, etc.) — or omit them at the SQL level. If your real source has actual PII, drop it at the SQL level before loading.
3. Size the predictive reasoner for the data with `reasoners.predictive.size` in `raiconfig.yaml` (a GPU size) if the call graph has more than ~50K subscribers; a deployed GNN runs on the device that size provides, and CPU works for ~1-10K subscribers.

> [!NOTE]
> There is no widely-known public telco churn dataset that includes a caller-to-callee call graph. The IBM Telco Customer Churn dataset (popular benchmark) is tabular only — no calls, no graph — so this template's GNN regression head doesn't add value over a tabular model on that benchmark. To exercise the graph path you need real CDR data or a synthetic call-graph generator.

## Troubleshooting

<details>
<summary><code>Experiment tracking database ... does not exist or is not accessible</code> when training</summary>

The GNN keeps its experiments and registered versions in the public schema named in `raiconfig.yaml`, and the RAI Native App needs USAGE on its database and schema plus CREATE EXPERIMENT and CREATE MODEL on the schema. Run the setup grants from the [Quickstart](#quickstart) as an administrator, then run `python train.py` again.
</details>

<details>
<summary>Predictions cluster around the segment mean</summary>

Expected on the bundled synthetic dataset — see the note after the output in Quickstart step 7. Real telco data with stronger churn-correlated features will produce more spread.

If your real-data run also produces flat predictions, check: are your continuous features on the same scale (the GNN doesn't normalize them), do you have enough train rows per segment after stratification, and is the target distribution wide enough for regression to beat the mean baseline?
</details>

<details>
<summary>The report prints <code>(no predictions returned)</code></summary>

The deployed model has not refreshed since a version was registered: the refresh that `rai models deploy` waits for runs before `python train.py`. Run `python train.py` if you haven't, then the refresh call from step 6 of the Quickstart, and query again.
</details>

## Learn more

### Core concepts

- [PyRel v1 query language](https://docs.relational.ai/) — concepts, properties, `count(...).per(...)` aggregates, and `select(...)` used to derive features and build the top-N report.

### Reasoner reference

- [Graph reasoner](https://docs.relational.ai/) — building a `Graph`, edge patterns, and PageRank on the call graph.
- [Predictive reasoner (GNN)](https://docs.relational.ai/) — `GNN` regression, `PropertyTransformer` feature declaration, train/validation/test tables, and predictions.

### CLI / SDK guides

- [Install and run PyRel](https://docs.relational.ai/get-started/install-and-run-pyrel/) — installing the SDK and configuring `raiconfig.yaml` to connect to your Snowflake account.

## Support

- File issues at the RelationalAI templates repository.

## Related templates

- **`fraud-detection`** — the canonical multi-reasoner GNN template (Graph + Rules + Predictive + Prescriptive). Use as the reference for adding a Prescriptive optimization stage on top of the GNN scores.
- **`demand_forecasting`** — sibling Predictive template using a regression GNN with a time column on retail sales data; useful as a pattern for time-aware GNN tasks.
