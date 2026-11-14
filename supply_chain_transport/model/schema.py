"""Semantic schema for the supply chain transport template: freight, transport types, LTL segments."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("supply_chain_transport")
Concept, Property = model.Concept, model.Property

# Concept: freight groups with inventory and transport time windows
FreightGroup = Concept("FreightGroup", identify_by={"name": String})
FreightGroup.inv_start_t = Property(f"{FreightGroup} has {Integer:inv_start_t}")
FreightGroup.inv_end_t = Property(f"{FreightGroup} has {Integer:inv_end_t}")
FreightGroup.tra_start_t = Property(f"{FreightGroup} has {Integer:tra_start_t}")
FreightGroup.tra_end_t = Property(f"{FreightGroup} has {Integer:tra_end_t}")
FreightGroup.arr_start_t = Property(f"{FreightGroup} has {Integer:arr_start_t}")
FreightGroup.arr_end_t = Property(f"{FreightGroup} has {Integer:arr_end_t}")
FreightGroup.inv_start = Property(f"{FreightGroup} has {Float:inv_start}")

# Concept: transport types (TL and LTL) with transit times
TransportType = Concept("TransportType", identify_by={"name": String})
TransportType.transit_time = Property(f"{TransportType} has {Integer:transit_time}")

# Concept: LTL cost segments (piecewise linear cost structure)
LTLSegment = Concept("LTLSegment", identify_by={"seg": Integer})
LTLSegment.limit = Property(f"{LTLSegment} has {Float:limit}")
LTLSegment.cost = Property(f"{LTLSegment} has {Float:cost}")
