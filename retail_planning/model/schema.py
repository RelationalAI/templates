"""Semantic schema for the retail planning template: the H&M graph concepts, the sales task relationships, and the optimizer inputs."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("retail_planning")
Concept, Relationship = model.Concept, model.Relationship

# Core entity concepts; their properties come from the bundled CSV columns.
Customer = Concept("Customer", identify_by={"c_customer_id": Integer})
Article = Concept("Article", identify_by={"a_article_id": Integer})
Transaction = Concept("Transaction", identify_by={"transaction_id": Integer})

# Sales regression task tables and relationships (transaction-level).
TrainTable = Concept("TrainTable")
ValTable = Concept("ValTable")
TestTable = Concept("TestTable")

Train = Relationship(f"{Transaction} at {String:timestamp} has {Float:value}")
Val = Relationship(f"{Transaction} at {String:timestamp} has {Float:value}")
Test = Relationship(f"{Transaction} at {String:timestamp}")

# OptArticle (optimizer scope) with pricing/inventory
OptArticle = Concept("OptArticle", identify_by={"opt_article_id": Integer})
OptArticle.name = model.Property(f"{OptArticle} has {String:name}")
OptArticle.initial_price = model.Property(f"{OptArticle} has {Float:initial_price}")
OptArticle.cost = model.Property(f"{OptArticle} has {Float:cost}")
OptArticle.initial_inventory = model.Property(
    f"{OptArticle} has {Integer:initial_inventory}")
OptArticle.salvage_rate = model.Property(f"{OptArticle} has {Float:salvage_rate}")

# Markdown optimization inputs
Discount = Concept("Discount", identify_by={"level": Integer})
Discount.discount_pct = model.Property(f"{Discount} has {Float:discount_pct}")
Discount.demand_lift = model.Property(f"{Discount} has {Float:demand_lift}")

Week = Concept("Week", identify_by={"num": Integer})
Week.demand_multiplier = model.Property(f"{Week} has {Float:demand_multiplier}")

# Demand/inventory planning inputs
ProdCapacity = Concept("ProdCapacity", identify_by={"pc_article_id": Integer})
ProdCapacity.max_production_per_week = model.Property(
    f"{ProdCapacity} has {Integer:max_production_per_week}")
ProdCapacity.production_cost = model.Property(
    f"{ProdCapacity} has {Float:production_cost}")
ProdCapacity.holding_cost_per_week = model.Property(
    f"{ProdCapacity} has {Float:holding_cost_per_week}")
ProdCapacity.pc_initial_inventory = model.Property(
    f"{ProdCapacity} has {Float:pc_initial_inventory}")
