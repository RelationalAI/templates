"""Failure timeline: the units, defective units, and final-test failure rate of each build week,
and the build week in which the failure spike starts."""

from relationalai.semantics import Float, Integer
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std import floats

from .schema import Unit, model

# A week is part of the spike when its failure rate exceeds this multiple of
# the opening (earliest) week's rate.
SPIKE_RATE_FACTOR = 2.0

BuildWeek = model.Concept("BuildWeek", identify_by={"week": Integer})
BuildWeek.n_units = model.Property(f"{BuildWeek} has {Integer:n_units}")
BuildWeek.n_defective = model.Property(f"{BuildWeek} has {Integer:n_defective}")
BuildWeek.failure_rate = model.Property(f"{BuildWeek} has {Float:failure_rate}")
model.define(BuildWeek.new(week=Unit.build_week))
_built_that_week = Unit.build_week == BuildWeek.week
model.define(
    BuildWeek.n_units(aggs.count(Unit).per(BuildWeek).where(_built_that_week)),
    BuildWeek.n_defective(
        aggs.count(Unit).per(BuildWeek).where(_built_that_week, Unit.is_defective()) | 0
    ),
)
model.define(
    BuildWeek.failure_rate(floats.float(BuildWeek.n_defective) / floats.float(BuildWeek.n_units))
)

# Spiking weeks fail at more than SPIKE_RATE_FACTOR times the opening week's
# rate; the spike onset is the earliest of them (none when no week spikes).
BuildWeek.is_spiking = model.Relationship(f"{BuildWeek} fails well above the opening week")
_opening, _week, _any_week = BuildWeek.ref(), BuildWeek.ref(), BuildWeek.ref()
model.where(
    _opening.week == aggs.min(_any_week.week),
    _week.failure_rate > SPIKE_RATE_FACTOR * _opening.failure_rate,
).define(_week.is_spiking())
SpikeOnset = model.Relationship(f"the failure spike starts in build week {Integer:week}")
_spiking = BuildWeek.ref()
model.define(SpikeOnset(aggs.min(_spiking.week).where(_spiking.is_spiking())))
