"""Semantic schema for the test data generation template: tables with row-count targets."""

from relationalai.semantics import Integer, Model, String

model = Model("test_data_generation")
Concept, Property = model.Concept, model.Property

# Concept: database tables with row count targets
Table = Concept("Table", identify_by={"table_name": String})
Table.target_rows = Property(f"{Table} has {Integer:target_rows}")
Table.min_rows = Property(f"{Table} has {Integer:min_rows}")
Table.max_rows = Property(f"{Table} has {Integer:max_rows}")
Table.priority = Property(f"{Table} has {Integer:priority}")
