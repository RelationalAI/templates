"""
<Your model name> ontology definition.

Defines the RAI model for <your domain> data.
Copy this file to ontology.py and customize it for your dataset.

Import `initialize` into any script that needs to build or query the model.
"""
import os as _os

import relationalai.semantics as rai
from relationalai.semantics import String


def _read_source_table() -> str:
    """Read source_table from rai-agent-config.yaml; fall back to inline constant.

    The YAML is present when running locally or in test_queries.py.
    It is not packaged into the Snowflake sproc, so the fallback fires there —
    which is fine because the value was correct when the sproc was last deployed.
    """
    _config_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "rai-agent-config.yaml")
    try:
        import yaml as _yaml
        with open(_config_path) as _f:
            return _yaml.safe_load(_f)["model"]["source_table"]
    except (FileNotFoundError, KeyError, ImportError):
        return "MY_DB.MY_SCHEMA.MY_TABLE"   # fallback — update to match your config


SOURCE_TABLE = _read_source_table()


def initialize(model: rai.Model):
    """
    <Replace with a description of your ontology.>

    This docstring is exposed to the agent via SourceCodeVerbalizer — write it
    as a concise summary of what the model represents, what concepts exist, and
    any important design decisions a user asking questions should know about.

    Example:
        Nodes are assembly parts connected in a parent/child BOM hierarchy sourced
        from MY_DB.MY_SCHEMA.MY_TABLE. Each node has a category (TYPE_A, TYPE_B,
        etc.) and an optional label (e.g. FLAGGED, REVIEWED).
    """
    src = model.Table(SOURCE_TABLE)

    # -------------------------------------------------------------------------
    # Concepts
    # -------------------------------------------------------------------------
    # Primary entity: identified by one or more string keys from the source table.
    # Use identify_by to deduplicate rows so each unique (key1, key2) becomes one
    # concept instance.
    Node = model.Concept("Node", identify_by={"id": String})

    # Edge table: one row = one parent→child link.
    # Only needed if your data has a hierarchy — remove otherwise.
    Edge = model.Concept(
        "Edge",
        identify_by={"parent_id": String, "child_id": String},
    )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------
    # Use model.Property for 1:1 (functional) attributes — required for
    # rai.per() groupby in queries. Each node must have at most one value.
    Node.category = model.Property(f"{Node} has category {String:category}")

    # Optional: label property for classified/flagged records.
    Node.label = model.Property(f"{Node} has label {String:label}")

    # -------------------------------------------------------------------------
    # Seed nodes from source table
    # -------------------------------------------------------------------------
    # Rows where the id column is null are skipped by null propagation.
    # Do NOT coalesce null ids to a sentinel — that causes FD violations on
    # Properties when multiple null rows get merged into the same node.
    model.define(
        p := Node.new(id=src.parent_id),
        p.category(src.parent_category),
    )
    model.define(
        c := Node.new(id=src.child_id),
        c.category(src.child_category),
    )

    # -------------------------------------------------------------------------
    # Seed edge table
    # -------------------------------------------------------------------------
    model.define(
        Edge.new(parent_id=src.parent_id, child_id=src.child_id)
    )

    # -------------------------------------------------------------------------
    # Seed known labels (optional)
    # -------------------------------------------------------------------------
    # Tag specific records with a classification label.
    # Add one .where() block per labelled record.
    #
    # node = Node.ref()
    # model.define(node.label("MY_LABEL")).where(node.id == "some-identifier")

    return Node, Edge
