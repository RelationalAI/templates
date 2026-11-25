"""Frontier analysis: which solves form the frontier and in what order, the marginal cost of each
service improvement along it, and the knee."""

from relationalai.semantics import Float, Integer, String, not_, where
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import math, strings

from .schema import FrontierPoint, model
from .shift_staffing import N_INTERIOR

# --------------------------------------------------
# Configure inputs
# --------------------------------------------------

# Smallest change that counts: a step that changes unmet demand by no more than this many
# patients is flat, and a rate of no more than this many dollars per patient is free.
TOLERANCE = 1e-6

# --------------------------------------------------
# Frontier points
# --------------------------------------------------

# Position 0 is the cheapest anchor, 1..N_INTERIOR the sweep, N_INTERIOR + 1 the
# best-service anchor.
FrontierPoint.label = model.Property(f"{FrontierPoint} has label {String:label}")
model.where(FrontierPoint.position == 0).define(FrontierPoint.label("cheapest"))
model.where(FrontierPoint.position == N_INTERIOR + 1).define(FrontierPoint.label("best_service"))
model.where(FrontierPoint.position >= 1, FrontierPoint.position <= N_INTERIOR).define(
    FrontierPoint.label(strings.concat("eps_", strings.string(FrontierPoint.position)))
)

# A solve is on the frontier when it solved to optimality and every sweep point up to it
# did: the frontier ends at the first sweep point that did not solve, and the best-service
# anchor is on it only when the whole sweep solved.
FrontierPoint.on_frontier = model.Relationship(f"{FrontierPoint} is on the frontier")
FrontierPoint.sweep_solved = model.Property(
    f"{FrontierPoint} follows {Integer:sweep_solved} optimal sweep points"
)
swept = FrontierPoint.ref()
model.define(FrontierPoint.sweep_solved(
    aggs.count(swept).per(FrontierPoint).where(
        swept.status == "OPTIMAL",
        swept.position >= 1,
        swept.position <= N_INTERIOR,
        swept.position <= FrontierPoint.position,
    )
))
model.where(FrontierPoint.position == 0, FrontierPoint.status == "OPTIMAL").define(
    FrontierPoint.on_frontier()
)
model.where(
    FrontierPoint.position >= 1,
    FrontierPoint.position <= N_INTERIOR,
    FrontierPoint.sweep_solved == FrontierPoint.position,
).define(FrontierPoint.on_frontier())
model.where(
    FrontierPoint.position == N_INTERIOR + 1,
    FrontierPoint.status == "OPTIMAL",
    FrontierPoint.sweep_solved == N_INTERIOR,
).define(FrontierPoint.on_frontier())

# The frontier's order: 1 for the cheapest anchor. The frontier is the positions from 0 up to
# its end, so point n is position n - 1.
FrontierPoint.number = model.Property(f"{FrontierPoint} is number {Integer:number} on the frontier")
model.where(FrontierPoint.on_frontier()).define(FrontierPoint.number(FrontierPoint.position + 1))

# --------------------------------------------------
# Marginal analysis
# --------------------------------------------------

# FrontierStep n is the move from frontier point n to point n + 1: the overtime cost it adds,
# the unmet demand it removes, and the dollars per patient that costs. A flat step removes
# no unmet demand and has no rate.
FrontierStep = model.Concept("FrontierStep", identify_by={"number": Integer})
FrontierStep.cost_added = model.Property(f"{FrontierStep} adds {Float:cost_added} of overtime cost")
FrontierStep.unmet_removed = model.Property(
    f"{FrontierStep} removes {Float:unmet_removed} of unmet demand"
)
FrontierStep.rate = model.Property(f"{FrontierStep} costs {Float:rate} per patient")
step_from, step_to = FrontierPoint.ref(), FrontierPoint.ref()
model.where(step_to.number == step_from.number + 1).define(
    FrontierStep.new(number=step_from.number)
)
model.where(FrontierStep.number == step_from.number, step_to.number == step_from.number + 1).define(
    FrontierStep.cost_added(step_to.overtime_cost - step_from.overtime_cost),
    FrontierStep.unmet_removed(step_from.unmet_demand - step_to.unmet_demand),
)
model.where(math.abs(FrontierStep.unmet_removed) > TOLERANCE).define(
    FrontierStep.rate(FrontierStep.cost_added / FrontierStep.unmet_removed)
)

# --------------------------------------------------
# Knee
# --------------------------------------------------

# When service improves for free before the first paid step, the knee is the last free
# point; otherwise it is the point after the step whose rate is the largest multiple of
# the rate before it. A rate ($ per patient) is never compared with a ratio. With no
# paid step there is no knee, and a frontier of fewer than two steps has none.
first_paid = Integer.ref()
paid_step = FrontierStep.ref()
FirstPaidStep = model.Relationship(f"the first step with a rate above zero is {Integer:number}")
model.define(FirstPaidStep(aggs.min(paid_step.number).where(paid_step.rate > TOLERANCE)))

# Free improvement: the knee is the point where the first paid step starts, and the figure
# is that step's rate.
FreeKnee = model.Relationship(
    f"the knee is frontier point {Integer:number}, the last free improvement, before a step "
    f"costing {Float:next_rate} per patient"
)
model.where(FirstPaidStep(first_paid), first_paid > 1, FrontierStep.number == first_paid).define(
    FreeKnee(first_paid, FrontierStep.rate)
)

# Largest jump: each paid step is followed by one at some multiple of its rate. The knee is
# the point after the step with the largest multiple above zero (the earliest on a tie),
# and the figure is that multiple. When no multiple is above zero the knee is point 2.
JumpKnee = model.Relationship(
    f"the knee is frontier point {Integer:number}, where marginal cost jumps {Float:jump} times"
)
FrontierStep.rate_multiple = model.Property(
    f"{FrontierStep} is followed by a step at {Float:rate_multiple} times its rate"
)
next_step, any_step = FrontierStep.ref(), FrontierStep.ref()
model.where(FrontierStep.rate > TOLERANCE, next_step.number == FrontierStep.number + 1).define(
    FrontierStep.rate_multiple(next_step.rate / FrontierStep.rate)
)
model.where(
    FirstPaidStep(first_paid),
    first_paid == 1,
    FrontierStep.rate_multiple > 0,
    aggs.rank(-FrontierStep.rate_multiple, FrontierStep.number) == 1,
).define(JumpKnee(FrontierStep.number + 1, FrontierStep.rate_multiple))
model.where(
    FirstPaidStep(first_paid),
    first_paid == 1,
    FrontierStep.number == 2,
    not_(where(any_step.rate_multiple > 0)),
).define(JumpKnee(2, 0.0))
