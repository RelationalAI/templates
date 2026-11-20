"""Load the sample freight groups, transport types, and LTL segments into the model."""

from pathlib import Path

from pandas import read_csv

from .schema import FreightGroup, LTLSegment, TransportType, model

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

fg_data = model.data(read_csv(DATA_DIR / "freight_groups.csv"))
model.define(FreightGroup.new(fg_data.to_schema()))

tl = TransportType.new(name="tl")
ltl = TransportType.new(name="ltl")
model.define(tl, tl.transit_time(2))
model.define(ltl, ltl.transit_time(3))

seg1 = LTLSegment.new(seg=1)
seg2 = LTLSegment.new(seg=2)
model.define(seg1, seg1.limit(6000.0), seg1.cost(0.18))
model.define(seg2, seg2.limit(7000.0), seg2.cost(0.12))
