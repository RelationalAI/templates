"""build_model: declare the ontology, load a source, and register the reasoning stages in order."""

from __future__ import annotations

import pandas as pd

from model.load import DataSource, load, load_links
from model.ontology import Onto, declare

# Stage order matters only for handle availability (rules themselves are declarative):
# families feed holdings; holdings feed control; control and phi feed everything after.
STAGES = ["family", "holdings", "control", "ownership", "close_links", "transactions", "patterns",
          "scoring", "explain", "cases"]


def _stage_fn(name):
    import importlib

    mod, fn = {
        "family": ("model.family", "register"),
        "holdings": ("model.control", "register_holdings"),
        "control": ("model.control", "register_control"),
        "ownership": ("model.ownership", "register"),
        "close_links": ("model.close_links", "register"),
        "transactions": ("model.transactions", "register"),
        "patterns": ("model.patterns", "register"),
        "scoring": ("model.scoring", "register"),
        "explain": ("model.explain", "register"),
        "cases": ("model.cases", "register"),
    }[name]
    return getattr(importlib.import_module(mod), fn)


def build_model(settings, source: DataSource, *, extra_links: pd.DataFrame | None = None,
                name: str = "bo_aml", stages: list[str] | None = None, config=None,
                augment: bool = False, gnn_account_probs: pd.DataFrame | None = None,
                gnn_pair_scores: pd.DataFrame | None = None) -> tuple[object, Onto]:
    """Build one model. `stages=None` registers every stage; `augment=True` adds the VADA-LINK
    candidate/scoring rules (needs Snowflake when BLOCKING_L1 uses a graph algorithm).
    gnn_account_probs (eid, prob) and gnn_pair_scores (a_eid, b_eid, score) are GNN outputs from
    Phase 8, fed back into the rules as data (P3's learning bus)."""
    from relationalai.semantics import Float, Model

    model = Model(name, config=config) if config is not None else Model(name)
    o = declare(model)
    o.settings = settings
    load(model, o, source)
    load_links(model, o, extra_links)
    if gnn_account_probs is not None and len(gnn_account_probs):
        o.Entity.gnn_account_prob = model.Property(f"{o.Entity} has GNN account risk {Float:prob}")
        d = model.data(gnn_account_probs[["eid", "prob"]].reset_index(drop=True).astype({"prob": float}))
        model.where(x := o.Entity.lookup(eid=d.eid)).define(x.gnn_account_prob(d.prob))
        o.has_gnn_account_probs = True
    for stage in (STAGES if stages is None else stages):
        _stage_fn(stage)(model, o, settings)
    if augment:
        from model import augmentation
        augmentation.register(model, o, settings, gnn_scores=gnn_pair_scores)
    return model, o
