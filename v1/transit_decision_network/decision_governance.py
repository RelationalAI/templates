"""DecisionPoint, proposal, review, and outcome layer of the transit ontology."""

from __future__ import annotations

from types import SimpleNamespace

from relationalai.semantics import Float, Integer, String


def add_decision_governance(model, Case, Event, history=None):
    Snapshot = model.Concept("InputSnapshot", identify_by={"id": String})
    SourceFile = model.Concept("SnapshotFile", identify_by={"id": String})
    CodeAsset = model.Concept("CodeAsset", identify_by={"id": String})
    Policy = model.Concept("PolicyVersion", identify_by={"id": String})
    Rule = model.Concept("DecisionRule", identify_by={"id": String})
    Point = model.Concept("DecisionPoint", identify_by={"id": String})
    Run = model.Concept("DecisionRun", identify_by={"id": String})
    Selection = model.Concept("RunSelection", identify_by={"id": String})
    Actor = model.Concept("DecisionActor", identify_by={"id": String})
    Action = model.Concept("DecisionAction", identify_by={"id": String})
    Outcome = model.Concept("OutcomeObservation", identify_by={"id": String})

    Snapshot.stage = model.Property(f"{Snapshot} has {String:stage}")
    Snapshot.input_hash = model.Property(f"{Snapshot} has {String:input_hash}")
    Snapshot.source_path = model.Property(f"{Snapshot} has {String:source_path}")
    SourceFile.snapshot = model.Property(f"{SourceFile} belongs to {Snapshot:snapshot}")
    SourceFile.filename = model.Property(f"{SourceFile} has {String:filename}")
    SourceFile.sha256 = model.Property(f"{SourceFile} has {String:sha256}")
    CodeAsset.kind = model.Property(f"{CodeAsset} has {String:kind}")
    CodeAsset.path = model.Property(f"{CodeAsset} has {String:path}")
    CodeAsset.sha256 = model.Property(f"{CodeAsset} has {String:sha256}")
    Policy.budget_usd = model.Property(f"{Policy} has {Float:budget_usd}")
    Policy.penalty_per_unmet_rider_usd = model.Property(
        f"{Policy} has {Float:penalty_per_unmet_rider_usd}")
    Rule.kind = model.Property(f"{Rule} has {String:kind}")
    Rule.description = model.Property(f"{Rule} has {String:description}")

    Point.case = model.Property(f"{Point} belongs to {Case:case}")
    Point.trigger = model.Property(f"{Point} was triggered by {Event:trigger}")
    Point.snapshot = model.Property(f"{Point} knew {Snapshot:snapshot}")
    Point.model_asset = model.Property(f"{Point} used {CodeAsset:model_asset}")
    Point.solver_asset = model.Property(f"{Point} used {CodeAsset:solver_asset}")
    Point.policy = model.Property(f"{Point} used {Policy:policy}")
    Point.known_at_utc = model.Property(f"{Point} occurred at {String:known_at_utc}")
    Point.trigger_reason = model.Property(f"{Point} has {String:trigger_reason}")

    Run.point = model.Property(f"{Run} evaluates {Point:point}")
    Run.kind = model.Property(f"{Run} has {String:kind}")
    Run.status = model.Property(f"{Run} has {String:status}")
    Run.solver = model.Property(f"{Run} used {String:solver}")
    Run.solver_version = model.Property(f"{Run} used {String:solver_version}")
    Run.objective_value = model.Property(f"{Run} has {Float:objective_value}")
    Run.plan_cost_usd = model.Property(f"{Run} has {Float:plan_cost_usd}")
    Run.unmet_riders = model.Property(f"{Run} has {Float:unmet_riders}")
    Run.accessibility_enforced = model.Property(f"{Run} has {Integer:accessibility_enforced}")
    Run.applies_rule = model.Relationship(f"{Run} applies {Rule}")

    Selection.run = model.Property(f"{Selection} belongs to {Run:run}")
    Selection.route_id = model.Property(f"{Selection} has {String:route_id}")
    Selection.zone_id = model.Property(f"{Selection} has {String:zone_id}")
    Selection.vehicle_id = model.Property(f"{Selection} has {String:vehicle_id}")
    Selection.driver_id = model.Property(f"{Selection} has {String:driver_id}")
    Selection.capacity = model.Property(f"{Selection} has {Float:capacity}")
    Selection.accessible_capacity = model.Property(f"{Selection} has {Float:accessible_capacity}")
    Selection.cost = model.Property(f"{Selection} has {Float:cost}")

    Actor.name = model.Property(f"{Actor} has {String:name}")
    Actor.role = model.Property(f"{Actor} has {String:role}")
    Action.run = model.Property(f"{Action} reviews {Run:run}")
    Action.actor = model.Property(f"{Action} was made by {Actor:actor}")
    Action.action = model.Property(f"{Action} has {String:action}")
    Action.action_at_utc = model.Property(f"{Action} happened at {String:action_at_utc}")
    Action.reason = model.Property(f"{Action} has {String:reason}")

    Outcome.run = model.Property(f"{Outcome} follows {Run:run}")
    Outcome.window_start_utc = model.Property(f"{Outcome} covers {String:window_start_utc}")
    Outcome.window_end_utc = model.Property(f"{Outcome} ends at {String:window_end_utc}")
    Outcome.observed_at_utc = model.Property(f"{Outcome} was recorded at {String:observed_at_utc}")
    Outcome.modeled_baseline_loss_usd = model.Property(
        f"{Outcome} has {Float:modeled_baseline_loss_usd}")
    Outcome.simulated_observed_loss_usd = model.Property(
        f"{Outcome} has {Float:simulated_observed_loss_usd}")
    Outcome.simulated_incremental_spend_usd = model.Property(
        f"{Outcome} has {Float:simulated_incremental_spend_usd}")
    Outcome.evidence_kind = model.Property(f"{Outcome} has {String:evidence_kind}")
    Outcome.estimated_benefit_usd = model.Property(f"{Outcome} has {Float:estimated_benefit_usd}")
    Outcome.estimated_net_value_usd = model.Property(f"{Outcome} has {Float:estimated_net_value_usd}")
    Outcome.estimated_roi = model.Property(f"{Outcome} has {Float:estimated_roi}")
    model.define(Outcome.estimated_benefit_usd(
        Outcome.modeled_baseline_loss_usd - Outcome.simulated_observed_loss_usd))
    model.define(Outcome.estimated_net_value_usd(
        Outcome.estimated_benefit_usd - Outcome.simulated_incremental_spend_usd))
    model.define(Outcome.estimated_roi(
        Outcome.estimated_net_value_usd / Outcome.simulated_incremental_spend_usd))

    if history is not None:
        def source(name):
            return model.data(history[name])

        snapshots = source("snapshots")
        model.define(item := Snapshot.new(id=snapshots.id), item.stage(snapshots.stage),
                     item.input_hash(snapshots.input_hash), item.source_path(snapshots.source_path))
        source_files = source("source_files")
        model.define(item := SourceFile.new(id=source_files.id),
                     item.snapshot(Snapshot.lookup(id=source_files.snapshot_id)),
                     item.filename(source_files.filename), item.sha256(source_files.sha256))
        assets = source("code_assets")
        model.define(item := CodeAsset.new(id=assets.id), item.kind(assets.kind),
                     item.path(assets.path), item.sha256(assets.sha256))
        policies = source("policies")
        model.define(item := Policy.new(id=policies.id), item.budget_usd(policies.budget_usd),
                     item.penalty_per_unmet_rider_usd(policies.penalty_per_unmet_rider_usd))
        rules = source("rules")
        model.define(item := Rule.new(id=rules.id), item.kind(rules.kind),
                     item.description(rules.description))
        points = source("points")
        model.define(item := Point.new(id=points.id), item.case(Case.lookup(id=points.case_id)),
                     item.trigger(Event.lookup(id=points.event_id)),
                     item.snapshot(Snapshot.lookup(id=points.snapshot_id)),
                     item.model_asset(CodeAsset.lookup(id=points.model_asset_id)),
                     item.solver_asset(CodeAsset.lookup(id=points.solver_asset_id)),
                     item.policy(Policy.lookup(id=points.policy_id)),
                     item.known_at_utc(points.known_at_utc),
                     item.trigger_reason(points.trigger_reason))
        runs = source("runs")
        model.define(item := Run.new(id=runs.id), item.point(Point.lookup(id=runs.point_id)),
                     item.kind(runs.kind), item.status(runs.status),
                     item.solver(runs.solver), item.solver_version(runs.solver_version),
                     item.objective_value(runs.objective_value),
                     item.plan_cost_usd(runs.plan_cost_usd),
                     item.unmet_riders(runs.unmet_riders),
                     item.accessibility_enforced(runs.accessibility_enforced))
        selections = source("selections")
        model.define(item := Selection.new(id=selections.id),
                     item.run(Run.lookup(id=selections.run_id)),
                     item.route_id(selections.route_id), item.zone_id(selections.zone_id),
                     item.vehicle_id(selections.vehicle_id), item.driver_id(selections.driver_id),
                     item.capacity(selections.capacity),
                     item.accessible_capacity(selections.accessible_capacity),
                     item.cost(selections.cost))
        actors = source("actors")
        model.define(item := Actor.new(id=actors.id), item.name(actors.name), item.role(actors.role))
        actions = source("actions")
        model.define(item := Action.new(id=actions.id), item.run(Run.lookup(id=actions.run_id)),
                     item.actor(Actor.lookup(id=actions.actor_id)),
                     item.action(actions.action), item.action_at_utc(actions.action_at_utc),
                     item.reason(actions.reason))
        outcomes = source("outcomes")
        model.define(item := Outcome.new(id=outcomes.id),
                     item.run(Run.lookup(id=outcomes.run_id)),
                     item.window_start_utc(outcomes.window_start_utc),
                     item.window_end_utc(outcomes.window_end_utc),
                     item.observed_at_utc(outcomes.observed_at_utc),
                     item.modeled_baseline_loss_usd(outcomes.modeled_baseline_loss_usd),
                     item.simulated_observed_loss_usd(outcomes.simulated_observed_loss_usd),
                     item.simulated_incremental_spend_usd(outcomes.simulated_incremental_spend_usd),
                     item.evidence_kind(outcomes.evidence_kind))
        run_rules = source("run_rules")
        model.define(Run.lookup(id=run_rules.run_id).applies_rule(
            Rule.lookup(id=run_rules.rule_id)))

    return SimpleNamespace(Snapshot=Snapshot, SourceFile=SourceFile, CodeAsset=CodeAsset,
                           Policy=Policy, Rule=Rule, Point=Point, Run=Run,
                           Selection=Selection, Actor=Actor, Action=Action,
                           Outcome=Outcome)
