"""Queryable decision lineage and illustrative actor ROI over the PyRel ontology."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.generate import DEFAULT_OUT
from decision_history import load_history
from relationalai.semantics.std import aggregates as aggs
from transit_model import build_model


def decision_lineage(ontology):
    """Show what source, event, model code, and policy each decision point knew."""
    model = ontology.model
    Point, Event = ontology.Point, ontology.Event
    Snapshot, CodeAsset, Policy = ontology.Snapshot, ontology.CodeAsset, ontology.Policy
    return model.where(
        Point.trigger == Event, Point.snapshot == Snapshot,
        Point.model_asset == CodeAsset, Point.policy == Policy,
    ).select(
        Point.id.alias("decision_point_id"), Point.known_at_utc.alias("known_at_utc"),
        Event.id.alias("trigger_event_id"), Event.actor.alias("trigger_actor"),
        Point.trigger_reason.alias("trigger_reason"),
        Snapshot.stage.alias("source_stage"), Snapshot.input_hash.alias("input_hash"),
        CodeAsset.sha256.alias("model_source_sha256"),
        Policy.id.alias("policy_version"), Policy.budget_usd.alias("budget_usd"),
    ).to_df().sort_values("known_at_utc")


def snapshot_files(ontology):
    """List each file fingerprint in the exact input snapshot for each point."""
    model = ontology.model
    Point, Snapshot, SourceFile = ontology.Point, ontology.Snapshot, ontology.SourceFile
    return model.where(Point.snapshot == Snapshot, SourceFile.snapshot == Snapshot).select(
        Point.id.alias("decision_point_id"), SourceFile.filename.alias("filename"),
        SourceFile.sha256.alias("sha256"),
    ).to_df().sort_values(["decision_point_id", "filename"])


def solver_code(ontology):
    """Identify the exact dispatch formulation source used at each point."""
    model = ontology.model
    Point, CodeAsset = ontology.Point, ontology.CodeAsset
    return model.where(Point.solver_asset == CodeAsset).select(
        Point.id.alias("decision_point_id"), CodeAsset.path.alias("path"),
        CodeAsset.sha256.alias("sha256"),
    ).to_df().sort_values("decision_point_id")


def applied_rules(ontology):
    """List the exact rule IDs used by each solver run, including the relaxed variant."""
    model = ontology.model
    Run, Point, Rule = ontology.Run, ontology.Point, ontology.Rule
    return model.where(Run.point == Point, Run.applies_rule(Rule)).select(
        Point.id.alias("decision_point_id"), Run.id.alias("run_id"),
        Run.kind.alias("run_kind"), Rule.id.alias("rule_id"),
        Rule.description.alias("rule_description"),
    ).to_df().sort_values(["decision_point_id", "run_kind", "rule_id"])


def decision_returns(ontology):
    """Trace approved proposals to a human actor and a synthetic outcome window."""
    model = ontology.model
    Point, Run = ontology.Point, ontology.Run
    Actor, Action, Outcome = ontology.Actor, ontology.Action, ontology.Outcome
    return model.where(
        Run.point == Point, Action.run == Run, Action.actor == Actor,
        Outcome.run == Run, Action.action == "approved",
        Run.kind == "policy_constrained",
        Outcome.evidence_kind == "synthetic_follow_up",
    ).select(
        Point.id.alias("decision_point_id"), Run.id.alias("run_id"),
        Actor.name.alias("actor"), Action.reason.alias("approval_reason"),
        Outcome.window_start_utc.alias("window_start_utc"),
        Outcome.window_end_utc.alias("window_end_utc"),
        Outcome.modeled_baseline_loss_usd.alias("modeled_baseline_loss_usd"),
        Outcome.simulated_observed_loss_usd.alias("simulated_observed_loss_usd"),
        Outcome.simulated_incremental_spend_usd.alias("simulated_incremental_spend_usd"),
        Outcome.estimated_benefit_usd.alias("estimated_benefit_usd"),
        Outcome.estimated_net_value_usd.alias("estimated_net_value_usd"),
        Outcome.estimated_roi.alias("estimated_roi"),
    ).to_df().sort_values("window_start_utc")


def actor_roi(ontology):
    """Rank reviewers by estimated return on approved, simulated decisions only.

    The numerator is summed estimated avoided disruption cost less summed realized
    incremental spend. It is divided by summed spend, not by averaging run ROIs.
    This synthetic comparison is not a causal or personnel-performance measure.
    """
    model = ontology.model
    Run, Actor, Action, Outcome = ontology.Run, ontology.Actor, ontology.Action, ontology.Outcome
    benefit = aggs.sum(Outcome.estimated_benefit_usd).per(Actor)
    spend = aggs.sum(Outcome.simulated_incremental_spend_usd).per(Actor)
    net = aggs.sum(Outcome.estimated_net_value_usd).per(Actor)
    return model.where(
        Action.actor == Actor, Action.run == Run, Outcome.run == Run,
        Action.action == "approved", Run.kind == "policy_constrained",
        Outcome.evidence_kind == "synthetic_follow_up",
    ).select(
        Actor.id.alias("actor_id"), Actor.name.alias("actor"),
        aggs.count(Outcome).per(Actor).alias("decisions"),
        benefit.alias("estimated_benefit_usd"),
        spend.alias("simulated_incremental_spend_usd"),
        net.alias("estimated_net_value_usd"),
        (net / spend).alias("estimated_roi"),
    ).to_df().sort_values("estimated_roi", ascending=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    history = load_history(args.ledger, args.source)
    ontology = build_model(args.source / "traffic_update", history=history)
    for name, query in (("decision_lineage", decision_lineage),
                        ("actor_roi", actor_roi),
                        ("decision_returns", decision_returns)):
        print(json.dumps({"query": name, "rows": query(ontology).to_dict(orient="records")},
                         sort_keys=True, default=str))


if __name__ == "__main__":
    main()
