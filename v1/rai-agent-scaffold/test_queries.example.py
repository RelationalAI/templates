"""
Quick smoke test: run both agent queries locally against the source table.

Copy this file to test_queries.py, update it to match your ontology.py and
queries.py, then run:
    RAI_CONFIG_FILE_PATH=raiconfig.yaml python test_queries.py
"""
import relationalai.semantics as rai
from relationalai.config import create_config, SnowflakeConnection

from ontology import initialize

print("Connecting to Snowflake...")
session = create_config().get_session(SnowflakeConnection)
print(f"Connected: {session.get_current_account()} / {session.get_current_role()}\n")

model = rai.Model("MY_MODEL_TEST")
Node, Edge = initialize(model)

# ---- Query 1: count by category --------------------------------------------
print("=" * 60)
print("QUERY 1: count_by_category")
print("=" * 60)
node = Node.ref()
cat  = node.category
g    = rai.per(cat)
# Note: local .to_df() may return one row per (node, category) because `node`
# remains a free variable. .drop_duplicates() gives the correct per-category
# summary. The deployed sproc returns correctly aggregated results.
df1 = model.select(
    cat.alias("category"),
    g.count(node).alias("count"),
).to_df().drop_duplicates()
print(df1.to_string(index=False))
print()

# ---- Query 2: label trace --------------------------------------------------
print("=" * 60)
print("QUERY 2: label_trace")
print("=" * 60)
n      = Node.ref()
edge   = Edge.ref()
parent = Node.ref()

df2 = model.select(
    n.label.alias("label"),
    n.category.alias("child_category"),
    n.id.alias("child_id"),
    parent.category.alias("parent_category"),
    parent.id.alias("parent_id"),
).where(
    n.label,
    n.id      == edge.child_id,
    parent.id == edge.parent_id,
).to_df()
print(df2.to_string(index=False))
print()
print("Done.")
