"""Semantic schema for the underwriting_audit template: age buckets and coverage bands."""

from relationalai.semantics import Integer, Model

model = Model("underwriting_audit")

# Concept: representative age bucket. Each row maps an integer
# bucket id to a representative age (in years) used to drive the
# senior indicator. Categorical age (rather than per-year integer)
# keeps the decision domain compact and similar in size to coverage
# band, which is what makes the multi-solution enumeration produce
# structurally varied witnesses across age and coverage rather than
# shifting one year at a time.
AgeBucket = model.Concept("AgeBucket", identify_by={"id": Integer})
AgeBucket.age_years = model.Property(f"{AgeBucket} has {Integer:age_years}")

# Concept: representative coverage band. Used purely as a
# categorical decision dimension so witnesses spread across coverage
# values; coverage does not enter the (buggy) ruleset under audit
# here, but real underwriting rules typically mix it in -- the
# column is left in place so customising the ruleset to include
# coverage thresholds is a one-IC change.
CoverageBand = model.Concept("CoverageBand", identify_by={"id": Integer})
CoverageBand.coverage_dollars = model.Property(f"{CoverageBand} has {Integer:coverage_dollars}")
