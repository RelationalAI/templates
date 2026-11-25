"""Semantic schema for the test data generation template: tables with row-count targets."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("test_data_generation")
Concept, Property = model.Concept, model.Property

# Concept: database tables with row count targets
Table = Concept("Table", identify_by={"table_name": String})
Table.target_rows = Property(f"{Table} has {Integer:target_rows}")
Table.min_rows = Property(f"{Table} has {Integer:min_rows}")
Table.max_rows = Property(f"{Table} has {Integer:max_rows}")
Table.priority = Property(f"{Table} has {Integer:priority}")

# Concept: foreign keys, one per child-table column, with the children per parent row the
# schema and constraints allow and the share of parent rows that must have a child.
ForeignKey = Concept("ForeignKey", identify_by={"child": Table, "column_name": String})
ForeignKey.parent = Property(f"{ForeignKey} references {Table}")
ForeignKey.min_per = Property(f"{ForeignKey} has at least {Integer:min_per} children per parent")
ForeignKey.max_per = Property(f"{ForeignKey} has at most {Integer:max_per} children per parent")
ForeignKey.coverage = Property(f"{ForeignKey} covers {Float:coverage} of its parent rows")
