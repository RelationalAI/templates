"""Prediction metrics: the row counts of the loaded tables, and the test-set accuracy, ROC-AUC, and
class distributions of the published predictions against the held-out labels."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

from .schema import People, Related, TestTable, TrainTable, ValidationTable, model

# Declares SmokerPrediction, the published predictions these metrics score.
from .smoker_gnn import SmokerPrediction

# The number of rows in each loaded table.
DataSummary = model.Relationship(
    f"the data has {Integer:people} people, {Integer:related} related pairs, and "
    f"{Integer:train} train, {Integer:validation} validation, {Integer:test} test rows"
)
model.define(
    DataSummary(
        aggs.count(People),
        aggs.count(Related),
        aggs.count(TrainTable),
        aggs.count(ValidationTable),
        aggs.count(TestTable),
    )
)

# A scored observation is a prediction joined to a held-out test row of the same person, so a
# person with several test rows is scored once per row. The scored cohort is those observations,
# and how many of them the prediction matches.
_scored = SmokerPrediction.person_id == TestTable.Id
_actual = TestTable.smoking
TestCohort = model.Relationship(
    f"the test cohort has {Integer:n_test} scored predictions, {Integer:n_correct} of them correct"
)
model.define(
    TestCohort(
        aggs.count(SmokerPrediction, TestTable).where(_scored),
        aggs.count(SmokerPrediction, TestTable).where(
            _scored, SmokerPrediction.predicted_label == _actual
        )
        | 0,
    )
)
_n_test, _n_correct = Integer.ref(), Integer.ref()
TestAccuracy = model.Relationship(f"the test accuracy is {Float:accuracy}")
model.where(TestCohort(_n_test, _n_correct), _n_test > 0).define(
    TestAccuracy(floats.float(_n_correct) / floats.float(_n_test))
)

# The share of the scored cohort in each class of the binary task, by held-out label and by
# predicted label (zero for a class that never occurs).
ClassShare = model.Concept("ClassShare", identify_by={"label": Integer})
ClassShare.n_actual = model.Property(f"{ClassShare} has {Integer:n_actual} held-out labels")
ClassShare.n_predicted = model.Property(f"{ClassShare} has {Integer:n_predicted} predicted labels")
ClassShare.actual_share = model.Property(f"{ClassShare} has held-out share {Float:actual_share}")
ClassShare.predicted_share = model.Property(
    f"{ClassShare} has predicted share {Float:predicted_share}"
)
model.define(ClassShare.new(label=0), ClassShare.new(label=1))
model.define(
    ClassShare.n_actual(
        aggs.count(SmokerPrediction, TestTable)
        .per(ClassShare)
        .where(_scored, _actual == ClassShare.label)
        | 0
    ),
    ClassShare.n_predicted(
        aggs.count(SmokerPrediction, TestTable)
        .per(ClassShare)
        .where(_scored, SmokerPrediction.predicted_label == ClassShare.label)
        | 0
    ),
)
model.where(TestCohort(_n_test, _n_correct), _n_test > 0).define(
    ClassShare.actual_share(floats.float(ClassShare.n_actual) / floats.float(_n_test)),
    ClassShare.predicted_share(floats.float(ClassShare.n_predicted) / floats.float(_n_test)),
)

# Rank-based ROC-AUC: (sum of the positives' ranks - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg),
# where tied probabilities share the average of their ranks. A level is one distinct probability
# among the scored observations; its observations occupy ranks n_up_to - n_scored + 1 through
# n_up_to, so they share the average rank n_up_to - (n_scored - 1) / 2.
ScoreLevel = model.Concept("ScoreLevel", identify_by={"probability": Float})
ScoreLevel.n_scored = model.Property(f"{ScoreLevel} has {Integer:n_scored} scored observations")
ScoreLevel.n_positive = model.Property(f"{ScoreLevel} has {Integer:n_positive} positives")
ScoreLevel.n_up_to = model.Property(f"{ScoreLevel} has {Integer:n_up_to} observations up to it")
ScoreLevel.mean_rank = model.Property(f"{ScoreLevel} has average rank {Float:mean_rank}")
model.where(_scored).define(ScoreLevel.new(probability=SmokerPrediction.probability))
_at_level = SmokerPrediction.probability == ScoreLevel.probability
model.define(
    ScoreLevel.n_scored(
        aggs.count(SmokerPrediction, TestTable).per(ScoreLevel).where(_scored, _at_level)
    ),
    ScoreLevel.n_positive(
        aggs.count(SmokerPrediction, TestTable)
        .per(ScoreLevel)
        .where(_scored, _at_level, _actual == 1)
        | 0
    ),
)
model.define(ScoreLevel.n_up_to(aggs.cumsum_asc(ScoreLevel.probability, ScoreLevel.n_scored)))
model.define(
    ScoreLevel.mean_rank(
        floats.float(ScoreLevel.n_up_to) - (floats.float(ScoreLevel.n_scored) - 1.0) / 2.0
    )
)

# The ROC-AUC is defined when the scored cohort has both classes; its positives are the
# held-out class-1 count.
PositiveRankSum = model.Relationship(f"the scored positives have rank sum {Float:rank_sum}")
model.define(
    PositiveRankSum(aggs.sum(ScoreLevel, ScoreLevel.n_positive * ScoreLevel.mean_rank))
)
TestAuc = model.Relationship(f"the test ROC-AUC is {Float:auc}")
_n_positive, _rank_sum = Integer.ref(), Float.ref()
model.where(
    PositiveRankSum(_rank_sum),
    TestCohort(_n_test, _n_correct),
    ClassShare.label == 1,
    ClassShare.n_actual(_n_positive),
    _n_positive > 0,
    _n_test > _n_positive,
).define(
    TestAuc(
        (_rank_sum - floats.float(_n_positive) * (floats.float(_n_positive) + 1.0) / 2.0)
        / (floats.float(_n_positive) * floats.float(_n_test - _n_positive))
    )
)
