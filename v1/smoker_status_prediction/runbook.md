# Smoker Status Prediction — Analyst Runbook

A health analytics team wants to predict whether a person smokes from routine biosignal screening data — and to let each person's prediction borrow signal from people they're related to, not just their own labs. The dataset is ~39,000 people with health attributes (age, blood pressure, cholesterol, hemoglobin, and more), ~58,000 "related" person-to-person edges, and train/validation/test smoking labels. The analysis builds a person-to-person graph and trains a graph neural network (GNN) to classify smoking status.

```text
38,984 people (health attributes) + 58,355 related-person edges → People↔People graph
      │
      ▼
/rai-predictive-modeling + /rai-predictive-training
   • GNN binary node classification: predict smoking from health attributes,
     message-passing over the related-people graph
   • train 31,187 / validation 3,898 / test 3,899   -> test ROC-AUC 0.848, accuracy 0.764
```

Each prompt is pasted into a fresh agent session loaded with the named `/rai-*` skill (named at the start of each prompt). They run in order in a single session — the predictive step reads the `People` concept and the related-person graph the build step created. (This trains a GNN on the RelationalAI engine.)

---

## 1. Build the ontology

**Prompt:** /rai-build-starter-ontology Build an ontology from `data/people.csv` (each person has an id and health-screening attributes — age, height, weight, blood pressure, fasting blood sugar, cholesterol, triglyceride, HDL, LDL, hemoglobin, and more), `data/related.csv` (an edge list pairing two people who are related), and the `data/train.csv`, `data/validation.csv`, and `data/test.csv` tables that carry the smoking label for each split. Model "related" as a relationship between people.

**Response:** Loads `People` (38,984, with the health-screening attributes), a `Related` person-to-person edge list (58,355 edges), and the train / validation / test label tables (31,187 / 3,898 / 3,899 people, each with a `smoking` flag).

## 2. Examine the ontology

**Prompt:** /rai-querying What concepts and relationships does the ontology have, and how many rows are in each?

**Response:** `People` (38,984, with health attributes), a `Related` self-relationship (58,355 person-to-person edges), and the labeled splits — 31,187 train, 3,898 validation, 3,899 test. The test split is scored by the model.

## 3. Train the smoker classifier

**Prompt:** /rai-predictive-modeling + /rai-predictive-training Train a graph neural network to predict each person's smoking status (binary classification) from their health-screening attributes, using the related-person edges as the GNN's message-passing graph so a person's prediction draws on their neighbors. Train on the training split, validate, and evaluate on the held-out test split with ROC-AUC and accuracy.

**Response:** A GNN binary node-classifier trains over the People↔People related-graph (features are the health-screening attributes) and evaluates on the 3,899 test people at **ROC-AUC ≈ 0.848 and accuracy ≈ 0.764**. Predictions are written back per person. (Metrics vary by a few hundredths across runs; the ~0.85 AUC is the stable read.)

## 4. Read the results

**Prompt:** /rai-predictive-training How well does the model separate smokers from non-smokers, and what does the score mean operationally?

**Response:** A test **ROC-AUC of about 0.85** means the model ranks a random smoker above a random non-smoker ~85% of the time — strong separation from routine biosignals plus the relational graph — at about **76% accuracy**. The per-person predicted probabilities let the team rank-order people by smoking likelihood (e.g. for screening or outreach) rather than relying on a single hard threshold.

## Data

Bundled CSVs in `data/`: 38,984 people with health attributes, 58,355 related-person edges, and train/validation/test smoking labels. `smoker_status_prediction_local.py` is the primary runnable (loads the CSVs via `model.data()`, trains the GNN on the RelationalAI engine); `smoker_status_prediction.py` is the Snowflake-tables reference. Full model in `smoker_status_prediction_local.py`.
