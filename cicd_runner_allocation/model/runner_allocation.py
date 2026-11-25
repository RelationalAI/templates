"""Runner allocation decision problems: three concurrency scenarios and a maintenance outage with its
conflict, and each solve's load per runner."""

import warnings

from relationalai.semantics import Float, Integer, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

from .schema import Assignment, Compatibility, Runner, Workflow, model
from .source import OFFLINE_RUNNERS

# Assignment domain: only compatible (workflow, runner) pairs exist.
model.define(Assignment.new(workflow=Compatibility.workflow, runner=Compatibility.runner))

# Scenario parameter: concurrency cap multiplier.
# 1.0 = use each runner's default max_concurrent.
# 0.5 = half capacity (maintenance window / cost reduction).
# 1.5 = burst mode (temporary scale-up).
SCENARIO_PARAM = "concurrency_multiplier"
SCENARIO_VALUES = [0.5, 1.0, 1.5]

# --------------------------------------------------
# One decision problem per scenario, and one for the outage
# --------------------------------------------------

# Each scenario is its own Problem, so an infeasible one leaves the others solved. Each
# Problem's status, cost, assignments, and runner loads are keyed by the scenario value
# ("outage" for the maintenance outage, which also publishes its conflict).
problems = {}
SolveStatus = {}
TotalCost = {}
Assigned = {}
RunnerLoad = {}
Stranded = {}
BindingCap = {}


def declare_allocation(key, name, concurrency_multiplier, offline_runners=(), conflict=False):
    """Declare runner assignment under a concurrency cap as a Problem and publish its results.

    ``offline_runners`` takes the named runners offline (a maintenance outage) by
    excluding their assignments. ``conflict=True`` requests a conflict analysis (an IIS)
    on the same solve, and publishes the stranded jobs and the binding runner caps.
    """
    # This builder runs once per scenario (the concurrency sweep, then the outage).
    # Building the Problem -- with its per-workflow and per-runner *named*
    # constraints -- that many times trips PyRel's "rules created in a loop"
    # heuristic. The pattern is intentional here (re-solving with a different cap is
    # the point) and harmless at this size, and the per-instance names are what let
    # the IIS read back by entity key. RAI diagnostics route through Python's
    # warnings module, so silence just that one message, scoped to this builder --
    # warning state outside it is untouched.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"\[Rules created in a loop\]")

        problem = Problem(model, Float, name=name)

        # Decision variable: binary assignment of workflow to runner. A maintenance
        # outage drops the offline runners' assignments via where=. With no offline
        # runners the comprehension is empty and `[] or None` collapses to None --
        # solve_for treats an empty where= and None the same ("no filter"); the
        # `or None` just makes the no-filter case explicit. `populate=False` keeps the
        # four Problems from writing the same `Assignment.x_assigned` property; each one's
        # values are published below as its own `Assigned` relationship.
        where_clause = [Assignment.runner.name != r for r in offline_runners] or None
        assign_var = problem.solve_for(
            Assignment.x_assigned,
            type="bin",
            name=["assign", Assignment.workflow.name, Assignment.runner.name],
            where=where_clause,
            populate=False,
        )

        AssignRef = Assignment.ref()
        # The assignments that have variables: an offline runner's have none.
        online = [AssignRef.runner.name != r for r in offline_runners]

        # Constraint: each workflow assigned to exactly one runner. ``keyed_by`` declares
        # the workflow key, so IIS membership reads back by it (assign_one.workflow); the
        # per-workflow name is a readable label.
        assign_one = problem.satisfy(
            model.where(AssignRef.workflow == Workflow, *online).require(
                sum(AssignRef.x_assigned).where(AssignRef.workflow == Workflow).per(Workflow) == 1
            ),
            name=["assign_one", Workflow.name],
            keyed_by={"workflow": Workflow},
        )

        # Constraint: per-runner concurrency limit (scaled by scenario multiplier),
        # over the online runners with assignments. ``keyed_by`` declares the runner
        # key (conc.runner).
        conc = problem.satisfy(
            model.where(AssignRef.runner == Runner, *online).require(
                sum(AssignRef.x_assigned).where(AssignRef.runner == Runner).per(Runner)
                <= concurrency_multiplier * Runner.max_concurrent
            ),
            name=["concurrency", Runner.name],
            keyed_by={"runner": Runner},
        )

        # Objective: minimize total pipeline cost.
        problem.minimize(
            sum(
                Assignment.x_assigned
                * Assignment.runner.cost_per_minute
                * Assignment.workflow.estimated_minutes
            )
        )

        # Each refresh of the deployed model runs this solve.
        problem.configure("highs", time_limit_sec=60, conflict=conflict)

    # The solve's status and cost, which the deployed model publishes for the queries.
    SolveStatus[key] = model.Relationship(f"{name} solve status is {String:status}")
    TotalCost[key] = model.Relationship(f"{name} total pipeline cost is {Float:cost}")
    model.define(SolveStatus[key](problem.termination_status()), TotalCost[key](problem.objective_value()))

    # The chosen assignments (value above 0.5), which the deployed model publishes for the
    # queries: the workflow and the runner.
    Assigned[key] = model.Relationship(f"{name} assigns {Workflow} to {Runner}")
    value_ref = Float.ref()
    model.where(assign_var.values(0, value_ref), value_ref > 0.5).define(
        Assigned[key](assign_var.assignment.workflow, assign_var.assignment.runner)
    )

    # Each runner's load: how many jobs it runs and their names in alphabetical order, joined
    # with commas (the id keeps jobs that share a name). A runner with no job has no row. It is
    # a relationship of its own, not a property of Runner: a property computed from the
    # solution on a concept the solve reads fails the deploy.
    RunnerLoad[key] = model.Relationship(
        f"{name} loads {Runner} with {Integer:n_jobs} jobs {String:workflows}"
    )
    runs = Assigned[key](Workflow, Runner)
    model.define(RunnerLoad[key](
        Runner,
        aggs.count(Workflow).per(Runner).where(runs),
        aggs.string_join(Workflow.name, sep=", ", index=[Workflow.name, Workflow.workflow_id])
        .per(Runner)
        .where(runs),
    ))

    if conflict:
        # The conflict, which the deployed model publishes for the queries. ``in_conflict``
        # is a bare predicate on each constraint instance -- true when the solver reports
        # that instance in the conflict (it collapses the solver's IN_CONFLICT and
        # MAYBE_IN_CONFLICT into a single membership). The declared entity key
        # (assign_one.workflow / conc.runner) joins the IIS to the actual stranded jobs
        # and the binding runner cap -- no rule-name parsing.
        Stranded[key] = model.Relationship(f"{name} has stranded {Workflow}")
        model.where(assign_one.in_conflict).define(Stranded[key](assign_one.workflow))
        BindingCap[key] = model.Relationship(f"{name} has binding cap {Runner}")
        model.where(conc.in_conflict).define(BindingCap[key](conc.runner))
        # The solve's metadata, which carries the conflict status the report checks before
        # reading the conflict (problem.solve_info() reads it from the deployed model).
        problem.install_solve_info()

    problems[key] = problem


for multiplier in SCENARIO_VALUES:
    declare_allocation(
        multiplier,
        "cicd_runner_allocation_concurrency_" + str(multiplier).replace(".", "_"),
        multiplier,
    )

# Maintenance outage: the offline runners strand the high-CPU Linux jobs, so this solve is
# infeasible on purpose; its conflict analysis names what makes it unschedulable.
declare_allocation(
    "outage",
    "cicd_runner_allocation_outage",
    1.0,
    offline_runners=OFFLINE_RUNNERS,
    conflict=True,
)
