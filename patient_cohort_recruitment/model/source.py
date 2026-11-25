"""Load the sample genes, therapies, patients, and event tables, and check them before the solve."""

from pathlib import Path

from pandas import read_csv

from .schema import (
    AdverseEvent,
    AdverseEventOcc,
    Gene,
    GeneIsA,
    MutationEvent,
    Patient,
    Therapy,
    TherapyEvent,
    model,
)

# The kinase-pathway-root gene anchors the ontology closure. Genes
# reachable from this root via `is_a` edges are the "kinase pathway
# members" -- exactly the genes whose mutations make a patient
# pathway-eligible.
KINASE_ROOT_GENE_ID = 1

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --------------------------------------------------
# Load all CSVs upfront so pre-solve invariants can validate the data
# integrity before any model.define rules are installed.
# --------------------------------------------------

genes_csv = read_csv(DATA_DIR / "genes.csv")
isa_csv = read_csv(DATA_DIR / "gene_is_a.csv")
therapies_csv = read_csv(DATA_DIR / "therapies.csv")
ae_terms_csv = read_csv(DATA_DIR / "ae_terms.csv")
patients_csv = read_csv(DATA_DIR / "patients.csv")
mut_csv = read_csv(DATA_DIR / "mutation_events.csv")
th_csv = read_csv(DATA_DIR / "therapy_events.csv")
ae_csv = read_csv(DATA_DIR / "adverse_events.csv")

# --------------------------------------------------
# Pre-solve invariants
#
# Catch the most common silent-failure modes before the solver runs:
# duplicate keys (would collapse rows), dangling FKs (would silently
# drop joins), a missing kinase-pathway root (would empty the closure
# and produce zero eligible patients), and negative timestamps (would
# break the AE-window predicate). Each helper raises a focused
# ValueError with the offending rows; replace the bundled CSVs with
# your own data and these guards become your first-pass data-quality
# check.
# --------------------------------------------------


def _assert_no_nulls(df, cols, source):
    cols = cols if isinstance(cols, list) else [cols]
    null_cols = [c for c in cols if df[c].isna().any()]
    if null_cols:
        raise ValueError(
            f"{source} has null/NaN values in column(s) {null_cols}. Required "
            f"columns must be fully populated; drop or impute the offending rows."
        )


def _assert_unique_keys(df, key, source):
    cols = key if isinstance(key, list) else [key]
    _assert_no_nulls(df, cols, source)
    dupe_rows = df[df.duplicated(subset=cols, keep=False)]
    if not dupe_rows.empty:
        duplicates = sorted({tuple(row) for row in dupe_rows[cols].itertuples(index=False)})
        raise ValueError(
            f"{source} has duplicate ({', '.join(cols)})={duplicates}. "
            f"Each key must be unique; remove or merge the conflicting rows."
        )


def _assert_root_gene_exists(genes_csv, root_id):
    _assert_no_nulls(genes_csv, "id", "genes.csv")
    if root_id not in set(int(g) for g in genes_csv["id"].tolist()):
        raise ValueError(
            f"KINASE_ROOT_GENE_ID={root_id} is not in genes.csv. The pathway "
            f"closure starts from this gene; supply a valid gene id or pick "
            f"one from genes.csv."
        )


def _assert_no_dangling_fks(child_df, child_col, parent_df, parent_col, source, parent_source):
    _assert_no_nulls(child_df, child_col, source)
    parent_ids = set(int(v) for v in parent_df[parent_col].unique())
    dangling = sorted({int(v) for v in child_df[child_col].unique() if int(v) not in parent_ids})
    if dangling:
        raise ValueError(
            f"{source}.{child_col} references unknown {parent_col}={dangling} "
            f"that does not appear in {parent_source}.{parent_col}. Every "
            f"foreign key must resolve."
        )


def _assert_nonneg_column(df, col, source):
    _assert_no_nulls(df, col, source)
    bad = sorted({int(v) for v in df[col].tolist() if int(v) < 0})
    if bad:
        raise ValueError(
            f"{source} has negative {col}={bad}. {col} must be >= 0 (days "
            f"since the patient's enrollment / index date)."
        )


# Validate primary-key uniqueness on every table.
for _df, _key, _src in [
    (genes_csv, "id", "genes.csv"),
    (isa_csv, ["child_id", "parent_id"], "gene_is_a.csv"),
    (therapies_csv, "id", "therapies.csv"),
    (ae_terms_csv, "id", "ae_terms.csv"),
    (patients_csv, "id", "patients.csv"),
    (mut_csv, "id", "mutation_events.csv"),
    (th_csv, "id", "therapy_events.csv"),
    (ae_csv, "id", "adverse_events.csv"),
]:
    _assert_unique_keys(_df, _key, _src)

_assert_root_gene_exists(genes_csv, KINASE_ROOT_GENE_ID)

# Foreign-key edges in the schema. Each row says "<source>.<col>
# references <parent_source>.<parent_col>". Update this table when
# you add a new event table or rewire a FK; the loop below validates
# every edge in one place.
_FK_EDGES = [
    (isa_csv, "child_id", genes_csv, "id", "gene_is_a.csv", "genes.csv"),
    (isa_csv, "parent_id", genes_csv, "id", "gene_is_a.csv", "genes.csv"),
    (mut_csv, "patient_id", patients_csv, "id", "mutation_events.csv", "patients.csv"),
    (mut_csv, "gene_id", genes_csv, "id", "mutation_events.csv", "genes.csv"),
    (th_csv, "patient_id", patients_csv, "id", "therapy_events.csv", "patients.csv"),
    (th_csv, "therapy_id", therapies_csv, "id", "therapy_events.csv", "therapies.csv"),
    (ae_csv, "patient_id", patients_csv, "id", "adverse_events.csv", "patients.csv"),
    (ae_csv, "ae_term_id", ae_terms_csv, "id", "adverse_events.csv", "ae_terms.csv"),
]
for _cdf, _ccol, _pdf, _pcol, _csrc, _psrc in _FK_EDGES:
    _assert_no_dangling_fks(_cdf, _ccol, _pdf, _pcol, _csrc, _psrc)

# Non-negativity check on event timestamps.
for _df, _col, _src in [
    (mut_csv, "t_days", "mutation_events.csv"),
    (th_csv, "t_days", "therapy_events.csv"),
    (ae_csv, "t_days", "adverse_events.csv"),
]:
    _assert_nonneg_column(_df, _col, _src)

# Genes and the `is_a` edges between them. The Graph reasoner closes the
# edges in `model/reasoning.py`.
model.define(Gene.new(model.data(genes_csv).to_schema()))

isa_data = model.data(isa_csv)
model.define(GeneIsA.new(child_id=isa_data.child_id, parent_id=isa_data.parent_id))
model.define(GeneIsA.parent(Gene)).where(GeneIsA.parent_id == Gene.id)
model.define(GeneIsA.child(Gene)).where(GeneIsA.child_id == Gene.id)

# Therapies, adverse-event terms, and patients.
model.define(Therapy.new(model.data(therapies_csv).to_schema()))
model.define(AdverseEvent.new(model.data(ae_terms_csv).to_schema()))
model.define(Patient.new(model.data(patients_csv).to_schema()))

# Mutation events.
mut_data = model.data(mut_csv)
model.define(MutationEvent.new(id=mut_data.id, t_days=mut_data.t_days))
model.define(MutationEvent.patient(Patient)).where(
    MutationEvent.id(mut_data.id),
    Patient.id(mut_data.patient_id),
)
model.define(MutationEvent.gene(Gene)).where(
    MutationEvent.id(mut_data.id),
    Gene.id(mut_data.gene_id),
)

# Therapy events.
th_data = model.data(th_csv)
model.define(TherapyEvent.new(id=th_data.id, t_days=th_data.t_days))
model.define(TherapyEvent.patient(Patient)).where(
    TherapyEvent.id(th_data.id),
    Patient.id(th_data.patient_id),
)
model.define(TherapyEvent.therapy(Therapy)).where(
    TherapyEvent.id(th_data.id),
    Therapy.id(th_data.therapy_id),
)

# Adverse-event occurrences.
ae_data = model.data(ae_csv)
model.define(AdverseEventOcc.new(id=ae_data.id, t_days=ae_data.t_days))
model.define(AdverseEventOcc.patient(Patient)).where(
    AdverseEventOcc.id(ae_data.id),
    Patient.id(ae_data.patient_id),
)
model.define(AdverseEventOcc.term(AdverseEvent)).where(
    AdverseEventOcc.id(ae_data.id),
    AdverseEvent.id(ae_data.ae_term_id),
)
