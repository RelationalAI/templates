---
title: "Subscriber Retention"
description: "Telco churn-risk scoring: PageRank over a Subscriber→Subscriber call graph (Graph) plus aggregate-derived call-volume features feed a regression GNN (Predictive) that scores per-subscriber churn risk, then surfaces the highest-risk subscribers per segment for retention campaigns."
featured: false
private: true
experience_level: advanced
industry: "Telecommunications"
reasoning_types:
  - Graph
  - Predictive
tags:
  - GNN
  - Regression
  - Churn Prediction
  - Graph Features
  - Telco
  - Multi-Reasoner
---

# Subscriber Retention

## What this template is for

Telco retention teams need to score every active subscriber for churn risk so they can target proactive offers at the right people before contracts roll over. Traditional churn models lean on plan attributes (rate, term, auto-renew) and demographics; they ignore the network around each subscriber. This template wires a call-graph signal into the model: who you call, who calls you, and how central you sit in the call network all become features, and the **Predictive** reasoner trains a GNN regression head over them. The graph features come from the **Graph** reasoner (PageRank on the Subscriber→Subscriber call graph); aggregate-derived `outgoing_calls` / `incoming_calls` properties round out the per-subscriber feature row.

> [!IMPORTANT]
> The RelationalAI **predictive reasoner (GNN)** used in this template is in early access. The API surface (`GNN`, `PropertyTransformer`, task relationships) may still change between releases; check the `rai-predictive-modeling` and `rai-predictive-training` skills for current guidance before adapting to production data.

## Who this is for

- Telco data scientists building churn-risk scoring pipelines that combine static plan attributes with relational/network signal
- Retention marketers who need a per-subscriber risk score by segment to drive targeted offer campaigns
- ML engineers exploring GNN regression over heterogeneous customer graphs
- Teams already querying RelationalAI on a Subscriber/Plan/Call ontology who want to layer a predictive head onto it

Assumes familiarity with Python, basic ML concepts (regression, RMSE), and graph data structures.

## What you'll build

- **Graph**: PageRank on a directed Subscriber→Subscriber call graph, exposing each subscriber's "social influence" as a continuous GNN feature
- **Predictive**: a regression GNN on the call graph predicting `churn_risk_score` per subscriber from demographics + plan attributes + the PageRank feature + aggregate-derived `outgoing_calls` / `incoming_calls` properties
- **Reporting**: top-N highest-predicted-risk subscribers per segment, ready to drop into a retention campaign queue
- The whole pipeline runs end-to-end on a small bundled telco dataset (~1,200 subscribers, ~6,000 calls); no Snowflake source data setup, no GPU

## What's included

- **Runner**: `subscriber_retention.py` — runs the full Graph-feature + GNN-regression pipeline plus reporting on the bundled CSVs
- **Model**: `Subscriber` (with denormalized plan attributes), `Call` (edge-intermediary for the call graph), and three task-table concepts (`TrainTable`, `ValTable`, `TestTable`) carrying the churn-risk labels
- **Sample data**: small telco subset (subscribers + plans + call detail records); see [Sample data](#sample-data) below
- **Outputs**: subscriber/call counts, churn-risk distribution, GNN training/prediction metrics, top-5 highest-risk subscribers per segment, test-set RMSE

## Prerequisites

### Access

Any Snowflake account with the **RelationalAI Native App** installed. The bundled CSVs ship with the template; there is no source-table setup. The GNN trains on CPU.

The predictive reasoner needs a writable Snowflake schema where it can create experiments and models. The script defaults to `TELCO_ENRICHMENT.EXPERIMENTS` (configurable via `EXP_DATABASE` / `EXP_SCHEMA` near the top of the script). One-time setup, run as `ACCOUNTADMIN`:

```sql
-- Use a database you own (TELCO_ENRICHMENT shown; pick anything writable)
CREATE DATABASE IF NOT EXISTS TELCO_ENRICHMENT;
CREATE SCHEMA IF NOT EXISTS TELCO_ENRICHMENT.EXPERIMENTS;

GRANT USAGE ON DATABASE TELCO_ENRICHMENT TO APPLICATION RELATIONALAI;
GRANT ALL PRIVILEGES ON SCHEMA TELCO_ENRICHMENT.EXPERIMENTS TO APPLICATION RELATIONALAI;
```

### Tools

- Python >= 3.10
- RelationalAI Python SDK (`relationalai`)

## Quickstart

1. Download ZIP:
   ```bash
   curl -O https://docs.relational.ai/templates/zips/v1/subscriber_retention.zip
   unzip subscriber_retention.zip
   cd subscriber_retention
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

5. Run the experiments-schema setup DDL above (one-time per Snowflake account).

6. Run:
   ```bash
   python subscriber_retention.py
   ```

### Expected output (abbreviated)

Real numbers from a verified end-to-end run on the bundled subset (CPU, no external data). Exact predicted scores shift slightly with numerical noise.

```text
Subscribers: 1200  Calls: 6000
Splits: train=837  val=179  test=184  (stratified by SEGMENT)
CHURN_RISK_SCORE: min=0.05  mean=0.24  max=0.89

============================================================
Predictive: subscriber churn-risk regression GNN (CPU)
============================================================
=== Start GNN Training ===
  ✓ Step 1 completed (~30s)   # prepare dataset + GNN tables
  ✓ Step 2 completed (~2s)    # trainer config
  ✓ Step 3 completed (~6s)    # submit training job
=== Start GNN Prediction ===
  ✓ GNN Prediction Complete (~92s)

============================================================
Top 5 highest-predicted-risk subscribers per segment
============================================================

[BUDGET]
       sub_id segment     type  lifetime_value  actual_risk  predicted_risk
SUB-CON-00510  BUDGET CONSUMER         4912.42         0.18        0.239697
...

[ENTERPRISE_PREMIUM]
      sub_id            segment       type  lifetime_value  actual_risk  predicted_risk
SUB-ENT-0025 ENTERPRISE_PREMIUM ENTERPRISE       464629.41         0.17        0.256691
...

Test-set RMSE: 0.1386
```

> [!NOTE]
> On this small synthetic dataset the GNN converges close to the segment-mean risk (~0.24) — there isn't enough learnable signal in 837 training rows of synthetic plan/call data to spread the predictions out further. The template demonstrates the **pipeline shape**, not score quality. Pointed at real telco data with stronger churn-correlated features (tenure, billing-event history, support-ticket patterns), the same pipeline produces discriminative per-subscriber scores.

## Template structure

```text
.
├── README.md                       # this file
├── pyproject.toml                  # dependencies
├── subscriber_retention.py         # 3-stage pipeline on bundled CSVs (CPU)
└── data/
    └── telco_mini/
        ├── subscribers.csv         # ~1,200 subscribers with demographics + risk scores
        ├── plans_contracts.csv     # one row per active contract, joined onto Subscriber
        ├── call_detail_records.csv # ~6,000 caller→callee call records
        └── billing_events.csv      # billing-cycle records (not used by the default pipeline; available for customization)
```

## Sample data

Two ways to feed this template:

1. **Bundled (light)** — `data/telco_mini/` ships with the template ZIP. ~1,200 subscribers + ~6,000 calls + 1,200 plans. Demo data. The four identifier columns (`FIRST_NAME`, `LAST_NAME`, `EMAIL`, `PHONE`) are dropped at load time as unused features. No external setup. **Quickstart uses this.**
2. **Bring-your-own** — replace the four CSVs under `data/telco_mini/` with your own subscriber / plan / CDR exports (same column names) and re-run. There is no widely-known public telco churn dataset that includes a caller→callee call graph (the popular [IBM Telco Customer Churn](https://www.kaggle.com/datasets/blastchar/telco-customer-churn) benchmark is tabular only — no calls, no graph), so the GNN graph path requires real CDR data or a synthetic call-graph generator. See [Run on your own Snowflake data](#run-on-your-own-snowflake-data) for the loading pattern.

About the bundled mini set:

- **~1,200 subscribers** across five segments: `BUDGET`, `ENTERPRISE_PREMIUM`, `HIGH_VALUE_INFLUENCER`, `PREMIUM`, `STANDARD`
- **~6,000 call records** wired as Subscriber→Subscriber edges for the PageRank graph
- **`CHURN_RISK_SCORE` target** is a continuous 0-1 risk score sourced from the analyst-facing risk model in the source schema. Customers adapting this template would replace it with their own labelled churn ground-truth (binary outcome) — the regression scaffold transfers directly to a binary-classification task by switching `task_type` and the target type.

## Model overview

### Key entities

- **Subscriber** (`sub_id`): one customer with denormalized plan attributes (`plan_type`, `monthly_rate_usd`, `data_limit_gb`, `term_months`, `auto_renew`, etc.) plus demographic fields (`segment`, `subscriber_type`, `lifetime_value_usd`, `nps_score`, `signup_date`). Enriched at pipeline time with `pagerank` and `outgoing_calls` / `incoming_calls`.
- **Call**: one call record between two subscribers; serves only as the edge intermediary for the PageRank graph and the call-volume aggregates. Has no identity property — only the edges matter downstream.

### Pipeline stages

```text
Subscribers + Plans + Call records (bundled CSVs, denormalized to Subscriber)
  → Graph:       PageRank on the Subscriber→Subscriber call graph
                 + aggregate-derived outgoing_calls / incoming_calls
  → Predictive:  GNN regression on Subscriber.churn_risk_score (continuous 0-1)
  → Reporting:   top-N highest-predicted-risk subscribers per segment
```

## How it works

### 1. Build the call graph

A directed `Subscriber → Subscriber` graph with one edge per call record drives the PageRank score:

```python
call_graph = Graph(
    model,
    directed=True,
    weighted=False,
    node_concept=Subscriber,
    aggregator="sum",
)
caller = Subscriber.ref()
callee = Subscriber.ref()
call_ref = Call.ref()
model.define(call_graph.Edge.new(src=caller, dst=callee)).where(
    call_ref.caller_sub_id == caller.sub_id,
    call_ref.callee_sub_id == callee.sub_id,
)
```

PageRank is bound to a `Subscriber.pagerank` property so it shows up as a continuous feature for the GNN:

```python
pagerank_rel = call_graph.pagerank()
Subscriber.pagerank = model.Property(f"{Subscriber} has {Float:pagerank}")
sub_pr = Subscriber.ref()
score_pr = Float.ref()
model.define(sub_pr.pagerank(score_pr)).where(pagerank_rel(sub_pr, score_pr))
```

### 2. Derive call-volume features

Two count-based rules derive `outgoing_calls` and `incoming_calls` per subscriber. Each is a Property bound via a `count(Call).per(Subscriber)` aggregate:

```python
Subscriber.outgoing_calls = model.Property(f"{Subscriber} has {Integer:outgoing_calls}")
model.define(
    Subscriber.outgoing_calls(count(Call).per(Subscriber))
).where(Call.caller_sub_id == Subscriber.sub_id)

Subscriber.incoming_calls = model.Property(f"{Subscriber} has {Integer:incoming_calls}")
model.define(
    Subscriber.incoming_calls(count(Call).per(Subscriber))
).where(Call.callee_sub_id == Subscriber.sub_id)
```

These declarative rules feed the same `Subscriber` row that PageRank is attached to, so the GNN sees one feature row per subscriber with everything blended in.

### 3. Declare features and target (PropertyTransformer)

Categorical, continuous, and integer feature types are declared explicitly. PKs and target columns are dropped:

```python
pt = PropertyTransformer(
    drop=[Subscriber.sub_id, Subscriber.postal_code, Subscriber.churn_risk_score],
    category=[Subscriber.subscriber_type, Subscriber.segment, Subscriber.status,
              Subscriber.plan_type, Subscriber.auto_renew],
    continuous=[Subscriber.lifetime_value_usd, Subscriber.monthly_rate_usd,
                Subscriber.early_termination_fee_usd, Subscriber.pagerank],
    integer=[Subscriber.nps_score, Subscriber.data_limit_gb, Subscriber.term_months,
             Subscriber.outgoing_calls, Subscriber.incoming_calls],
    datetime=[Subscriber.signup_date],
)
```

### 4. Train and predict (GNN regression)

The split is stratified by `SEGMENT` so each segment's distribution carries through train/val/test. The GNN trains as a regression head with `eval_metric="rmse"`:

```python
gnn = GNN(
    exp_database=EXP_DATABASE,
    exp_schema=EXP_SCHEMA,
    graph=call_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=False,
    seed=SEED,
    device="cpu",
    n_epochs=20,
    lr=0.005,
)
gnn.fit()
Subscriber.predictions = gnn.predictions(domain=Test)
```

The prediction is bound back as `Subscriber.predictions` so downstream queries can pull `predicted_value` per subscriber.

### 5. Top-N per segment (Reporting)

A single declarative query joins predicted risk back to subscriber metadata and groups by segment:

```python
sub_ref = Subscriber.ref()
risk_ref = Float.ref()
results_df = (
    select(
        sub_ref.sub_id.alias("sub_id"),
        sub_ref.segment.alias("segment"),
        sub_ref.subscriber_type.alias("type"),
        sub_ref.lifetime_value_usd.alias("lifetime_value"),
        sub_ref.churn_risk_score.alias("actual_risk"),
        risk_ref.alias("predicted_risk"),
    )
    .where(sub_ref.predictions.predicted_value(risk_ref))
    .to_df()
)
```

## Customize this template

- **Switch to binary churn classification** — change `task_type="regression"` → `"binary_classification"` and set the train/val target to a Boolean churn outcome instead of a continuous risk score. The graph + rules stages stay identical.
- **Add weights to the call graph** — set `weighted=True` on the `Graph(...)` call and add an aggregated edge-weight property (e.g. total call-duration or call-count per pair). The PageRank scores will reflect call intensity, not just topology.
- **Bring more features in** — the bundled `billing_events.csv` is not used by the default pipeline. To wire it in as a billing-driven feature, add a `BillingEvent` concept and derive a `Subscriber.late_payment_count` rule from `PAYMENT_STATUS = "OVERDUE"`, then add it to the integer features in `PropertyTransformer`:

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
- **Adjust the segment stratification** — the default split stratifies by `SEGMENT`. For very imbalanced churn outcomes, stratify by the target instead (or in addition).
- **Repoint to your own subscriber data** — replace the CSVs under `data/telco_mini/` with your real subscriber/plan/CDR exports (same column names) and re-run.

### Run on your own Snowflake data

The bundled CSVs are loaded via `model.data(df)` for a no-setup local demo. To run against full data living in Snowflake instead:

1. Replace the three `pd.read_csv(...)` calls at the top of the script with Snowpark queries (or use `model.Table("<DB>.<SCHEMA>.<TABLE>")` directly per the `rai-pyrel-coding` skill's data-loading guidance):
   ```python
   from relationalai.config import SnowflakeConnection, create_config
   from snowflake import snowpark
   session: snowpark.Session = create_config().get_session(SnowflakeConnection)

   sub_df = session.sql("SELECT * FROM YOUR_DB.RAW.SUBSCRIBERS").to_pandas()
   plan_df = session.sql("SELECT * FROM YOUR_DB.RAW.PLANS_CONTRACTS").to_pandas()
   calls_df = session.sql("SELECT * FROM YOUR_DB.RAW.CALL_DETAIL_RECORDS").to_pandas()
   ```
2. Drop unused identifier columns the same way (`FIRST_NAME`, etc.) — or omit them at the SQL level. If your real source has actual PII, drop it at the SQL level before loading.
3. Bump the GNN's compute (`device="cuda"` and a GPU-backed RAI engine) if the call graph has more than ~50K subscribers; CPU works for ~1-10K subscribers.

> [!NOTE]
> There is no widely-known public telco churn dataset that includes a caller→callee call graph. The IBM Telco Customer Churn dataset (popular benchmark) is tabular only — no calls, no graph — so this template's GNN regression head doesn't add value over a tabular model on that benchmark. To exercise the graph path you need real CDR data or a synthetic call-graph generator.

## Troubleshooting

<details>
<summary><code>Schema does not exist or the GNN RelationalAI Native App lacks permissions</code> on first run</summary>

The GNN training service writes experiment artifacts to a Snowflake schema, and the `RELATIONALAI` native app must have write access. If the run fails with a message like *"The experiment is configured to use database 'X' and schema 'EXPERIMENTS' ... grant the necessary permissions ..."*, run the [setup DDL](#access) as `ACCOUNTADMIN`.

The error also fires if you've changed `EXP_DATABASE` to a database you own but haven't granted USAGE on the database itself; both grants (USAGE on database + ALL on schema) are required.
</details>

<details>
<summary>Train job stays in <code>QUEUED</code> with no progress</summary>

The GNN training job runs in a Snowpark Container Services service that the predictive reasoner provisions on demand. If the service can't come up (e.g. compute pool suspended, image-version mismatch in the RAI app manifest), submitted train jobs sit in `QUEUED` indefinitely.

Diagnose by checking server-side state:

```sql
-- Is the train job actually running?
SELECT ID, STATE, CREATED_ON, FINISHED_AT, ABORT_REASON
FROM RELATIONALAI.API.JOBS
WHERE PAYLOAD LIKE '%"job_type": "train"%'
ORDER BY CREATED_ON DESC LIMIT 5;
```

If `STATE='QUEUED'` for >5 minutes with nothing else `RUNNING`, the GNN service likely isn't accepting jobs — escalate to RelationalAI support rather than killing/restarting the script.
</details>

<details>
<summary>Predictions cluster around the segment mean</summary>

Expected on the bundled synthetic dataset — see the *Expected output* note. Real telco data with stronger churn-correlated features will produce more spread.

If your real-data run also produces flat predictions, check: are your continuous features on the same scale (the GNN doesn't normalize them), do you have enough train rows per segment after stratification, and is the target distribution wide enough for regression to beat the mean baseline?
</details>

<details>
<summary>Re-running with a stale experiment causes <code>training job failed</code> at the prediction step</summary>

The SDK matches submitted training jobs to existing experiments by name. If a previous failed run left a model_run_id behind, a re-run can match the stale model and fail trying to predict against incompatible artifacts. Bump the model name to force a fresh experiment:

```python
model = Model("subscriber_retention_local_v2")  # bump on each re-run if needed
```
</details>

## Related templates

- **`fraud-detection`** — the canonical multi-reasoner GNN template (Graph + Rules + Predictive + Prescriptive). Use as the reference for adding a Prescriptive optimization stage on top of the GNN scores.
- **`demand_forecasting`** — sibling Predictive template using a regression GNN with a time column on retail sales data; useful as a pattern for time-aware GNN tasks.
