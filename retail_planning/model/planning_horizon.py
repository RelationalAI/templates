"""Planning horizon: the number of weeks the markdown and demand/inventory problems plan over."""

from relationalai.semantics import Integer, count

from .schema import Week, model

num_weeks = model.Relationship(f"{Integer}")
model.define(num_weeks(count(Week)))
