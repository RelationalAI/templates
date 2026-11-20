"""Semantic schema for the water allocation template: sources, users, and connections."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("water_allocation")
Concept, Property = model.Concept, model.Property

# Source concept: water sources with capacity and cost.
Source = Concept("Source", identify_by={"id": Integer})
Source.name = Property(f"{Source} has {String:name}")
Source.capacity = Property(f"{Source} has {Float:capacity}")
Source.cost_per_unit = Property(f"{Source} has {Float:cost_per_unit}")

# User concept: water demand points with priority levels.
User = Concept("User", identify_by={"id": Integer})
User.name = Property(f"{User} has {String:name}")
User.demand = Property(f"{User} has {Float:demand}")
User.priority = Property(f"{User} has {Integer:priority}")

# Connection concept: links between sources and users.
Connection = Concept("Connection")
Connection.source = Property(f"{Connection} from {Source}", short_name="source")
Connection.user = Property(f"{Connection} to {User}", short_name="user")
Connection.max_flow = Property(f"{Connection} has {Float:max_flow}")
Connection.loss_rate = Property(f"{Connection} has {Float:loss_rate}")
