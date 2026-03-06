"""Supply Chain Transport (prescriptive optimization) template.

This script demonstrates a multi-mode transportation optimization model in RelationalAI:

- Load sample CSVs describing freight groups with inventory and transport time windows.
- Model freight groups, transport types (TL/LTL), and LTL cost segments as *concepts*
  with typed properties.
- Choose shipment quantities, transport mode indicators, and arrival days per freight group.
- Enforce inventory flow conservation, all-or-nothing shipment, capacity limits, and
  piecewise-linear LTL cost structure.
- Minimize total cost (inventory holding + TL fixed cost + LTL variable cost).

Run:
    `python supply_chain_transport.py`

Output:
    Prints the solver termination status, total cost, and tables showing inventory
    levels, transport quantities, and arrival days.
"""

from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Float, Integer, Model, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("supply_chain_transport")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

# Parameters
dep_start = 1
dep_end = 4
inv_cost = 0.1 / 100       # Inventory holding cost rate
tl_tra_cost = 2000.0       # Fixed cost per TL truck
tl_cap = 24000.0           # TL weight capacity

# Concept: freight groups with inventory and transport time windows
FreightGroup = Concept("FreightGroup", identify_by={"name": String})
FreightGroup.inv_start_t = Property(f"{FreightGroup} has {Integer:inv_start_t}")
FreightGroup.inv_end_t = Property(f"{FreightGroup} has {Integer:inv_end_t}")
FreightGroup.tra_start_t = Property(f"{FreightGroup} has {Integer:tra_start_t}")
FreightGroup.tra_end_t = Property(f"{FreightGroup} has {Integer:tra_end_t}")
FreightGroup.arr_start_t = Property(f"{FreightGroup} has {Integer:arr_start_t}")
FreightGroup.arr_end_t = Property(f"{FreightGroup} has {Integer:arr_end_t}")
FreightGroup.inv_start = Property(f"{FreightGroup} has {Float:inv_start}")
fg_data = model.data(read_csv(data_dir / "freight_groups.csv"))
model.define(FreightGroup.new(fg_data.to_schema()))

# Concept: transport types (TL and LTL) with transit times
TransportType = Concept("TransportType", identify_by={"name": String})
TransportType.transit_time = Property(f"{TransportType} has {Integer:transit_time}")
tl = TransportType.new(name="tl")
ltl = TransportType.new(name="ltl")
model.define(tl, tl.transit_time(2))
model.define(ltl, ltl.transit_time(3))

# Concept: LTL cost segments (piecewise linear cost structure)
LTLSegment = Concept("LTLSegment", identify_by={"seg": Integer})
LTLSegment.limit = Property(f"{LTLSegment} has {Float:limit}")
LTLSegment.cost = Property(f"{LTLSegment} has {Float:cost}")
seg1 = LTLSegment.new(seg=1)
seg2 = LTLSegment.new(seg=2)
model.define(seg1, seg1.limit(6000.0), seg1.cost(0.18))
model.define(seg2, seg2.limit(7000.0), seg2.cost(0.12))

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

departure_days = std.common.range(dep_start, dep_end + 1)
time_period_ref = Integer.ref()
FreightGroup_ref = FreightGroup.ref()

s = Problem(model, Float)

# Variable: inv[fg, t] = vendor inventory for freight group fg on day t
FreightGroup.x_inv = Property(f"{FreightGroup} on day {Integer:t} has {Float:inv}")
x_inv = Float.ref()
s.solve_for(
    FreightGroup.x_inv(time_period_ref, x_inv),
    lower=0,
    name=["x_inv", FreightGroup.name, time_period_ref],
    where=[time_period_ref == std.common.range(FreightGroup.inv_start_t, FreightGroup.inv_end_t + 1)]
)

# Variable: qty_tra/bin_tra = quantity shipped and binary indicator per (type, fg, day)
TransportType.x_qty_tra = Property(f"{TransportType} for {FreightGroup} on day {Integer:t} has {Float:qty_tra}")
TransportType.y_bin_tra = Property(f"{TransportType} for {FreightGroup} on day {Integer:t} has {Float:bin_tra}")
x_qty_tra = Float.ref()
y_bin_tra = Float.ref()
s.solve_for(
    TransportType.x_qty_tra(FreightGroup_ref, time_period_ref, x_qty_tra),
    lower=0,
    name=["x_qty_tra", TransportType.name, FreightGroup_ref.name, time_period_ref],
    where=[time_period_ref == std.common.range(FreightGroup_ref.tra_start_t, FreightGroup_ref.tra_end_t + 1)],
)
s.solve_for(
    TransportType.y_bin_tra(FreightGroup_ref, time_period_ref, y_bin_tra),
    type="bin",
    name=["y_bin_tra", TransportType.name, FreightGroup_ref.name, time_period_ref],
    where=[time_period_ref == std.common.range(FreightGroup_ref.tra_start_t, FreightGroup_ref.tra_end_t + 1)],
)

# Variable: arr_day[fg] = integer arrival day at destination
FreightGroup.z_arr_day = Property(f"{FreightGroup} has {Float:arr_day}")
s.solve_for(
    FreightGroup.z_arr_day,
    type="int",
    lower=FreightGroup.arr_start_t,
    upper=FreightGroup.arr_end_t,
    name=["z_arr_day", FreightGroup.name],
)

# Variable: weight[type, t] = total weight on transport type on day t
TransportType.x_weight = Property(f"{TransportType} on departure day {Integer:t} has {Float:weight}")
x_weight = Float.ref()
s.solve_for(
    TransportType.x_weight(time_period_ref, x_weight),
    lower=0,
    name=["x_weight", TransportType.name, time_period_ref],
    where=[time_period_ref == departure_days],
)

# Variable: y_bin_tl[t] = 1 if TL is used on departure day t
bin_tl = Property(f"departure day {Integer:t} has {Float:bin_tl}")
y_bin_tl = Float.ref()
s.solve_for(
    bin_tl(time_period_ref, y_bin_tl),
    type="bin",
    name=["y_bin_tl", time_period_ref],
    where=[time_period_ref == departure_days],
)

# Variable: rem_ltl/bin_ltl = piecewise linear LTL cost segment variables
LTLSegment.x_rem_ltl = Property(f"{LTLSegment} on departure day {Integer:t} has {Float:rem_ltl}")
LTLSegment.y_bin_ltl = Property(f"{LTLSegment} on departure day {Integer:t} has {Float:bin_ltl}")
x_rem_ltl = Float.ref()
y_bin_ltl = Float.ref()
s.solve_for(
    LTLSegment.x_rem_ltl(time_period_ref, x_rem_ltl),
    lower=0,
    name=["x_rem_ltl", LTLSegment.seg, time_period_ref],
    where=[time_period_ref == departure_days]
)
s.solve_for(
    LTLSegment.y_bin_ltl(time_period_ref, y_bin_ltl),
    type="bin",
    name=["y_bin_ltl", LTLSegment.seg, time_period_ref],
    where=[time_period_ref == departure_days]
)

# Constraint: inventory flow conservation (inv[t] = inv[t+1] + shipped)
s.satisfy(model.where(
    x_inv_current := Float.ref(),
    x_inv_next := Float.ref(),
    FreightGroup.x_inv(time_period_ref, x_inv_current),
    FreightGroup.x_inv(time_period_ref + 1, x_inv_next),
    TransportType.x_qty_tra(FreightGroup, time_period_ref, x_qty_tra),
).require(
    x_inv_current == x_inv_next + sum(x_qty_tra).per(FreightGroup, time_period_ref)
))

# Constraint: initial inventory equals starting position; final inventory is zero
s.satisfy(model.require(
    x_inv == FreightGroup.inv_start
).where(FreightGroup.x_inv(FreightGroup.inv_start_t, x_inv)))
s.satisfy(model.require(
    x_inv == 0
).where(FreightGroup.x_inv(FreightGroup.inv_end_t, x_inv)))

# Constraint: freight groups ship all-or-nothing
s.satisfy(model.require(
    x_qty_tra == FreightGroup.inv_start * y_bin_tra
).where(
    TransportType.x_qty_tra(FreightGroup, time_period_ref, x_qty_tra),
    TransportType.y_bin_tra(FreightGroup, time_period_ref, y_bin_tra),
))

# Constraint: arrival day = departure day + transit time
s.satisfy(model.require(
    FreightGroup.z_arr_day == sum((time_period_ref + TransportType.transit_time) * y_bin_tra).per(FreightGroup)
).where(TransportType.y_bin_tra(FreightGroup, time_period_ref, y_bin_tra)))

# Constraint: weight[type,t] = sum of quantities shipped by that type on day t
s.satisfy(model.require(
    x_weight == sum(x_qty_tra).per(TransportType, time_period_ref)
).where(
    TransportType.x_weight(time_period_ref, x_weight),
    TransportType.x_qty_tra(FreightGroup, time_period_ref, x_qty_tra),
))

# Constraint: TL weight <= capacity if TL is used
s.satisfy(model.require(
    x_weight <= tl_cap * y_bin_tl
).where(
    TransportType.name("tl"),
    TransportType.x_weight(time_period_ref, x_weight),
    bin_tl(time_period_ref, y_bin_tl),
))

# Constraint: piecewise LTL cost — exactly one segment active, remainder within limit
s.satisfy(model.require(
    sum(y_bin_ltl).per(time_period_ref) == 1,
    x_rem_ltl <= LTLSegment.limit * y_bin_ltl,
).where(
    LTLSegment.x_rem_ltl(time_period_ref, x_rem_ltl),
    LTLSegment.y_bin_ltl(time_period_ref, y_bin_ltl),
))

# Constraint: LTL weight decomposition
LTLSegment_outer = LTLSegment.ref()
LTLSegment_inner = LTLSegment.ref()
s.satisfy(model.where(
    LTLSegment_outer := LTLSegment.ref(),
    LTLSegment_inner := LTLSegment.ref(),
    TransportType.name("ltl"),
    TransportType.x_weight(time_period_ref, x_weight),
).require(
    x_weight ==
    sum(x_rem_ltl).where(LTLSegment.x_rem_ltl(time_period_ref, x_rem_ltl)).per(time_period_ref) +
    sum(LTLSegment_outer.limit * y_bin_ltl).where(
        LTLSegment_inner.y_bin_ltl(time_period_ref, y_bin_ltl),
        LTLSegment_outer.seg == LTLSegment_inner.seg - 1,
    ).per(time_period_ref)
))

# Objective: minimize total cost (inventory holding + TL fixed + LTL variable)
total_inv_cost = inv_cost * sum(x_inv).where(
    FreightGroup.x_inv(time_period_ref, x_inv), time_period_ref > FreightGroup.inv_start_t
)
total_tl_cost = tl_tra_cost * sum(y_bin_tl).where(bin_tl(Integer.ref(), y_bin_tl))
total_ltl_rem_cost = LTLSegment.cost * sum(x_rem_ltl).per(LTLSegment).where(
    LTLSegment.x_rem_ltl(Integer.ref(), x_rem_ltl)
)
LTLSegment_outer = LTLSegment.ref()
LTLSegment_inner = LTLSegment.ref()
total_ltl_bin_cost = (LTLSegment_outer.cost * LTLSegment_outer.limit) * sum(y_bin_ltl).per(LTLSegment_outer).where(
    LTLSegment_inner.y_bin_ltl(Integer.ref(), y_bin_ltl),
    LTLSegment_outer.seg == LTLSegment_inner.seg - 1,
)
total_cost = sum(model.union(total_inv_cost, total_tl_cost, total_ltl_rem_cost, total_ltl_bin_cost))
s.minimize(total_cost)

# --------------------------------------------------
# Solve and check solution
# --------------------------------------------------

s.display()
s.solve("highs", time_limit_sec=60, _server_side_import=False)
s.display_solve_info()

print(f"Status: {s.termination_status}")
print(f"Total cost: ${s.objective_value:.2f}")

# Extract solution via model.select() — properties are populated after solve
print("\n=== Inventory Levels ===")
inv_df = model.select(
    FreightGroup.name.alias("freight_group"), time_period_ref.alias("day"),
    x_inv.alias("inventory"),
).where(FreightGroup.x_inv(time_period_ref, x_inv)).to_df()
print(inv_df.to_string(index=False))

print("\n=== Transport Quantities ===")
qty_df = model.select(
    TransportType.name.alias("type"), FreightGroup_ref.name.alias("freight_group"),
    time_period_ref.alias("day"), x_qty_tra.alias("quantity"),
).where(
    TransportType.x_qty_tra(FreightGroup_ref, time_period_ref, x_qty_tra), x_qty_tra > 0.001
).to_df()
print(qty_df.to_string(index=False))

print("\n=== Arrival Days ===")
arr_df = model.select(
    FreightGroup.name.alias("freight_group"),
    FreightGroup.z_arr_day.alias("arrival_day"),
).to_df()
print(arr_df.to_string(index=False))
