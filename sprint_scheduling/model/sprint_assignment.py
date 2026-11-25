"""Sprint assignment: the first sprint each issue can be assigned to, and one
weighted-completion-time decision problem per capacity scenario."""

from relationalai.semantics import Float, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

from .schema import Assignment, Developer, Issue, Skill, Sprint, model

# EPOCH-TO-PERIOD MAPPING: an issue created before a sprint starts is eligible from that sprint,
# and one created during a sprint targets it, so the target is the first sprint that ends after
# the issue was created. An issue created after the last sprint ended targets the last sprint.
_ending_after, _last = Sprint.ref(), Sprint.ref()
model.define(
    Issue.target_sprint_number(
        aggs.min(_ending_after.number).per(Issue).where(Issue.created_at < _ending_after.enddate)
        | aggs.max(_last.number)
    )
)

# Build assignment domain: developer can work on issue if they have the matching skill,
# and the sprint is >= the issue's target sprint (can't assign to earlier sprints)
model.define(Assignment.new(developer=Developer, issue=Issue, sprint=Sprint)).where(
    Skill.developer_id == Developer.id,
    Skill.team == Issue.team,
    Sprint.number >= Issue.target_sprint_number,
)

# --------------------------------------------------
# Model the decision problem
# --------------------------------------------------

# Static constraint expression: each issue assigned exactly once (no scenario param dependency)
issue_once = model.require(sum(Assignment.x_assigned).per(Issue) == 1).where(
    Assignment.issue == Issue
)

# Static objective expression: minimize weighted completion time (no scenario param dependency)
# Lower priority number = higher urgency, so priority 1 issues cost more in later sprints
# Weight = (max_priority + 1 - priority) to make P1 issues most expensive to delay
max_priority = 3
weighted_completion = sum(
    Assignment.x_assigned
    * (max_priority + 1 - Assignment.issue.priority)
    * Assignment.sprint.number
)

# Scenarios (what-if: vary team capacity to see impact on sprint assignments)
SCENARIO_PARAM = "capacity_multiplier"
SCENARIO_VALUES = [0.35, 0.5, 1.0]

# --------------------------------------------------
# One decision problem per scenario
# --------------------------------------------------

# Each scenario is its own Problem, so an infeasible scenario leaves the others solved.
# Each Problem's status, objective, and assignments are keyed by the scenario value.
problems = {}
SolveStatus = {}
WeightedCompletion = {}
Assigned = {}

for scenario_value in SCENARIO_VALUES:
    capacity_multiplier = scenario_value
    name = "sprint_scheduling_capacity_" + str(scenario_value).replace(".", "_")

    problem = Problem(model, Float, name=name)

    # Variable: binary assignment (1 if issue assigned to developer in sprint, 0 otherwise)
    # `populate=False` keeps the three scenario Problems from writing the same
    # `Assignment.x_assigned` property; each scenario's values are read through its own
    # `assign_var.values(...)`, published below as that scenario's `Assigned` relationship.
    assign_var = problem.solve_for(
        Assignment.x_assigned,
        type="bin",
        name=[
            "assign",
            Assignment.issue.key,
            Assignment.developer.name,
            Assignment.sprint.name,
        ],
        populate=False,
    )

    # Static constraint: each issue assigned exactly once
    problem.satisfy(issue_once)

    # Parameterized constraint: developer capacity per sprint (references capacity_multiplier)
    problem.satisfy(
        model.require(
            sum(Assignment.x_assigned * Assignment.issue.story_points).per(
                Developer, Sprint
            )
            <= Developer.capacity_points_per_sprint * capacity_multiplier
        ).where(Assignment.developer == Developer, Assignment.sprint == Sprint)
    )

    # Static objective: minimize weighted completion time
    problem.minimize(weighted_completion)

    # Each refresh of the deployed model runs this solve.
    problem.configure("highs", time_limit_sec=60)

    # The solve's status and objective, which the deployed model publishes for the queries.
    SolveStatus[scenario_value] = model.Relationship(f"{name} solve status is {String:status}")
    WeightedCompletion[scenario_value] = model.Relationship(
        f"{name} weighted completion time is {Float:objective}"
    )
    model.define(
        SolveStatus[scenario_value](problem.termination_status()),
        WeightedCompletion[scenario_value](problem.objective_value()),
    )

    # The scenario's chosen assignments (value above 0.5), which the deployed model publishes
    # for the queries: the issue, the developer, and the sprint.
    Assigned[scenario_value] = model.Relationship(
        f"{name} assigns {Issue} to {Developer} in {Sprint}"
    )
    value_ref = Float.ref()
    model.where(assign_var.values(0, value_ref), value_ref > 0.5).define(
        Assigned[scenario_value](
            assign_var.assignment.issue,
            assign_var.assignment.developer,
            assign_var.assignment.sprint,
        )
    )
    problems[scenario_value] = problem
