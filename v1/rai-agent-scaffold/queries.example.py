"""
Pre-defined queries and ToolRegistry for the Cortex agent.

Copy this file to queries.py and customize the query functions for your dataset.

Each query function must:
  - Return a rai.Fragment (a model.select(...) expression)
  - Have a clear docstring — shown to the LLM to decide when to call the query
  - Have a __name__ attribute — used as the query identifier (preserved by functools.wraps)
"""
import functools

import relationalai.semantics as rai
from relationalai.semantics import Model
from relationalai.agent.cortex import (
    ToolRegistry,
    SourceCodeVerbalizer,
    QueryCatalog,
)

from ontology import initialize


def count_by_category(model: Model, Node, Edge) -> rai.Fragment:
    """
    Count of records grouped by category.
    Use this to answer questions like 'how many records of each type exist'
    or 'what is the breakdown by category'.
    Returns one row per category with the count of distinct records.
    """
    node = Node.ref()
    g    = rai.per(node.category)
    return model.select(
        node.category.alias("category"),
        g.count(node).alias("count"),
    )


def label_trace(model: Model, Node, Edge) -> rai.Fragment:
    """
    Traceability: every record tagged with a label and its immediate parent
    in the hierarchy — including the parent's category and identifier.
    Use this to answer questions like 'show me all flagged records and their
    parents' or 'which records are affected by a given label'.
    """
    n      = Node.ref()   # the labelled child node
    edge   = Edge.ref()   # the edge connecting child to parent
    parent = Node.ref()   # the immediate parent node
    return model.select(
        n.label.alias("label"),
        n.category.alias("child_category"),
        n.id.alias("child_id"),
        parent.category.alias("parent_category"),
        parent.id.alias("parent_id"),
    ).where(
        n.label,
        n.id      == edge.child_id,
        parent.id == edge.parent_id,
    )


def build_tool_registry(model: Model) -> ToolRegistry:
    """Build the ToolRegistry for the Cortex agent sproc."""
    Node, Edge = initialize(model)

    # Bind model/Node/Edge into each query so QueryCatalog gets zero-arg callables
    # while __name__ and __doc__ (used by the agent) are preserved via functools.wraps.
    def _bind(fn, *args):
        @functools.wraps(fn)
        def wrapper():
            return fn(*args)
        return wrapper

    return ToolRegistry().add(
        model=model,
        description=(
            "Replace this with a description of your domain model. "
            "The agent uses this text to decide when to query this model — "
            "describe what data it contains and what kinds of questions it can answer."
        ),
        verbalizer=SourceCodeVerbalizer(model, initialize),
        queries=QueryCatalog(
            _bind(count_by_category, model, Node, Edge),
            _bind(label_trace,       model, Node, Edge),
        ),
    )
