"""Semantic schema for the financial index replication template."""

from relationalai.semantics import Float, Model, String

model = Model("financial_index_replication")

Stock = model.Concept("Stock", identify_by={"ticker": String})
Stock.name = model.Property(f"{Stock} has name {String:name}")
Stock.sector = model.Property(f"{Stock} has sector {String:sector}")
Stock.benchmark_weight = model.Property(f"{Stock} has benchmark weight {Float:benchmark_weight}")
Stock.avg_dollar_volume = model.Property(
    f"{Stock} has average dollar volume {Float:avg_dollar_volume}"
)
Stock.previous_weight = model.Property(
    f"{Stock} has previous portfolio weight {Float:previous_weight}"
)

Sector = model.Concept("Sector", identify_by={"sector_name": String})
Sector.benchmark_weight = model.Property(
    f"{Sector} has benchmark weight {Float:sector_benchmark_weight}"
)
Stock.sector_ref = model.Relationship(f"{Stock} belongs to {Sector}")

ReturnMonth = model.Concept("ReturnMonth", identify_by={"date": String})
ReturnMonth.index_return = model.Property(f"{ReturnMonth} has index return {Float:index_return}")
Stock.monthly_return = model.Relationship(f"{Stock} on {ReturnMonth} has return {Float:stock_return}")
