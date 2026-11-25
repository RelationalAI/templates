"""Supplier risk: reliability and delay-risk flags, the avoid, watch, and reliable classes, late
shipments, and escalated demand."""

from relationalai.semantics import Float, Integer, String
from relationalai.semantics.std import aggregates as aggs

from .schema import Business, DelayPrediction, Demand, Shipment, model

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

DELAY_PROB_THRESHOLD = 0.15  # above this = high delay risk
RELIABILITY_THRESHOLD = 0.80  # below this = unreliable supplier
PREDICTION_QUARTER = "Q1-2025"  # which quarter's predictions to use

# --------------------------------------------------
# Stage 2: Rules -- supplier risk classification
# --------------------------------------------------

# Rule 2: Business is unreliable when reliability_score < threshold.
Business.is_unreliable = model.Relationship(f"{Business} is unreliable")
model.where(
    Business.reliability_score < RELIABILITY_THRESHOLD
).define(Business.is_unreliable())

# Rule 3: Business has high delay risk from ML predictions.
Business.has_high_delay_risk = model.Relationship(
    f"{Business} has high delay risk"
)
dp_ref = DelayPrediction.ref()
model.where(
    dp_ref.supplier_business(Business),
    dp_ref.fiscal_quarter == PREDICTION_QUARTER,
    dp_ref.predicted_delay_prob > DELAY_PROB_THRESHOLD,
).define(Business.has_high_delay_risk())

# Rule: Business is watch-level when it has either risk flag.
# "Avoid" businesses (both flags) are hard-blocked in Stage 3; watch-level
# businesses get a soft risk surcharge in the objective.
Business.is_watch_level = model.Relationship(f"{Business} is watch level")
model.where(Business.is_unreliable()).define(Business.is_watch_level())
model.where(Business.has_high_delay_risk()).define(Business.is_watch_level())

# Rule: Business is avoid when BOTH unreliable AND high delay risk fire.
Business.is_avoid = model.Relationship(f"{Business} is avoid")
model.define(Business.is_avoid()).where(
    Business.is_unreliable(),
    Business.has_high_delay_risk(),
)

# Rule 4: Demand is escalated when priority is HIGH.
Demand.is_escalated = model.Relationship(f"{Demand} is escalated")
model.where(Demand.priority == "HIGH").define(Demand.is_escalated())

# Supplier risk class, for each business that has a reliability score: avoid, else watch
# (watch level without avoid), else reliable.
Business.risk_class = model.Property(f"{Business} has risk class {String:risk_class}")
rated_score = Float.ref()
model.where(Business.reliability_score(rated_score), Business.is_avoid()).define(
    Business.risk_class("avoid")
)
model.where(
    Business.reliability_score(rated_score),
    Business.is_watch_level(),
    model.not_(Business.is_avoid()),
).define(Business.risk_class("watch"))
model.where(
    Business.reliability_score(rated_score),
    model.not_(Business.is_watch_level()),
).define(Business.risk_class("reliable"))

# Late shipments: a shipment with a recorded delay over 0 days. A shipment still in transit
# has no recorded delay and is not late.
Shipment.is_late = model.Relationship(f"{Shipment} is late")
model.where(Shipment.delay_days > 0).define(Shipment.is_late())

# Shipments from a supplier, and how many of them are late.
num_shipments = model.Relationship(f"there are {Integer:num_shipments} shipments from a supplier")
num_late_shipments = model.Relationship(
    f"there are {Integer:num_late_shipments} late shipments from a supplier"
)
shipper = Business.ref()
model.define(num_shipments(aggs.count(Shipment).where(Shipment.supplier(shipper)) | 0))
model.define(num_late_shipments(
    aggs.count(Shipment).where(Shipment.supplier(shipper), Shipment.is_late()) | 0
))

# Late shipments per supplier (a supplier with none has no count) and each supplier's rank by
# them, most first, ties broken by business id. The count is negated so both keys sort
# ascending, a form every backend ranks.
Business.late_shipment_count = model.Property(
    f"{Business} has {Integer:late_shipment_count} late shipments"
)
model.define(Business.late_shipment_count(
    aggs.count(Shipment).per(Business).where(Shipment.supplier(Business), Shipment.is_late())
))
Business.late_rank = model.Property(f"{Business} has late-shipment rank {Integer:late_rank}")
model.define(Business.late_rank(aggs.rank(-Business.late_shipment_count, Business.id)))

# Escalated demand orders.
num_escalated = model.Relationship(f"there are {Integer:num_escalated} escalated demands")
model.define(num_escalated(aggs.count(Demand).where(Demand.is_escalated()) | 0))
