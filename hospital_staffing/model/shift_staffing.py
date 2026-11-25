"""Shift staffing decision problems: two anchor solves and an epsilon-constraint sweep between
them."""

from relationalai.semantics import Float, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

from .schema import Assignment, FrontierPoint, Nurse, Shift, SweepPoint, model

# Number of epsilon-constraint points between the two anchors.
N_INTERIOR = 5

AssignmentRef = Assignment.ref()


# --------------------------------------------------
# Problem helper — shared constraints, parameterized objective
# --------------------------------------------------

def staffing_problem(name, position, objective="min_overtime", sweep_index=None):
    """Declare one staffing solve and publish its result as FrontierPoint `position`.

    objective: "min_overtime" (primary) or "min_unmet" (anchor 2 -- minimize unmet demand)
    sweep_index: if set, add constraint sum(unmet) <= that SweepPoint's eps_unmet
    Returns the solution's total unmet demand.
    """
    problem = Problem(model, Float, name=name)

    assign_var = problem.solve_for(
        Assignment.x_assigned,
        type="bin",
        populate=False,
        name=["assigned", Assignment.availability.nurse.name, Assignment.availability.shift.name],
    )

    overtime_var = problem.solve_for(
        Nurse.x_overtime_hours,
        type="cont",
        populate=False,
        name=["ot", Nurse.name],
        lower=0,
    )

    problem.solve_for(
        Shift.x_patients_served,
        type="cont",
        populate=False,
        name=["pt", Shift.name],
        lower=0,
    )

    unmet_var = problem.solve_for(
        Shift.x_unmet_demand,
        type="cont",
        populate=False,
        name=["ud", Shift.name],
        lower=0,
    )

    # Constraints

    # Can only assign if available
    problem.satisfy(model.where(Assignment).require(Assignment.x_assigned <= Assignment.availability.available))

    # Every nurse works at least one shift
    nurse_shift_count = sum(AssignmentRef.x_assigned).where(
        AssignmentRef.availability.nurse == Nurse).per(Nurse)
    problem.satisfy(model.where(AssignmentRef.availability.nurse == Nurse).require(nurse_shift_count >= 1))

    # Max 2 shifts per nurse
    problem.satisfy(model.where(AssignmentRef.availability.nurse == Nurse).require(nurse_shift_count <= 2))

    # Minimum nurses per shift
    shift_staff_count = sum(AssignmentRef.x_assigned).where(
        AssignmentRef.availability.shift == Shift).per(Shift)
    problem.satisfy(model.where(AssignmentRef.availability.shift == Shift).require(shift_staff_count >= Shift.min_nurses))

    # At least one nurse with required skill level per shift
    skilled = [
        AssignmentRef.availability.shift == Shift,
        AssignmentRef.availability.nurse.skill_level >= Shift.min_skill,
    ]
    skilled_coverage = sum(AssignmentRef.x_assigned).where(*skilled).per(Shift)
    problem.satisfy(model.where(*skilled).require(skilled_coverage >= 1))

    # Overtime >= total hours worked - regular hours
    total_hours_worked = sum(
        AssignmentRef.x_assigned * AssignmentRef.availability.shift.duration
    ).where(AssignmentRef.availability.nurse == Nurse).per(Nurse)
    problem.satisfy(model.where(AssignmentRef.availability.nurse == Nurse).require(
        Nurse.x_overtime_hours >= total_hours_worked - Nurse.regular_hours
    ))

    # Patients served <= demand per shift
    problem.satisfy(model.where(Shift).require(Shift.x_patients_served <= Shift.patient_demand))

    # Patients served <= nursing capacity per shift
    shift_nursing_capacity = shift_staff_count * Shift.patients_per_nurse_hour * Shift.duration
    problem.satisfy(model.where(AssignmentRef.availability.shift == Shift).require(
        Shift.x_patients_served <= shift_nursing_capacity
    ))

    # Unmet demand >= patient demand - patients served
    problem.satisfy(model.where(Shift).require(Shift.x_unmet_demand >= Shift.patient_demand - Shift.x_patients_served))

    # --- Epsilon constraint: a sweep point caps total unmet demand at its eps ---
    if sweep_index is not None:
        problem.satisfy(model.where(SweepPoint.index == sweep_index).require(
            sum(Shift.x_unmet_demand) <= SweepPoint.eps_unmet
        ))

    # --- Objective ---
    overtime_cost = sum(Nurse.x_overtime_hours * Nurse.hourly_cost * Nurse.overtime_multiplier)

    if objective == "min_overtime":
        problem.minimize(overtime_cost)
    elif objective == "min_unmet":
        problem.minimize(sum(Shift.x_unmet_demand))

    # Each refresh of the deployed model runs this solve.
    problem.configure("highs", time_limit_sec=60)

    # --- Publish the result ---
    # The solve's status, overtime cost, unmet demand, and assignments, which the deployed
    # model publishes for the queries. populate=False: read Variable.values, not the properties.
    status, hours, unmet, assigned = String.ref(), Float.ref(), Float.ref(), Float.ref()
    model.where(problem.termination_status()(status)).define(
        FrontierPoint.new(position=position, status=status)
    )
    solution_overtime_cost = sum(
        overtime_var, hours * overtime_var.nurse.hourly_cost * overtime_var.nurse.overtime_multiplier
    ).where(overtime_var.values(0, hours))
    solution_unmet = sum(unmet_var, unmet).where(unmet_var.values(0, unmet))
    model.where(FrontierPoint.position == position).define(
        FrontierPoint.overtime_cost(solution_overtime_cost),
        FrontierPoint.unmet_demand(solution_unmet),
    )
    model.where(
        FrontierPoint.position == position, assign_var.values(0, assigned), assigned > 0.5,
    ).define(FrontierPoint.assigns(assign_var.assignment.availability.nurse, assign_var.assignment.availability.shift))

    return solution_unmet


# --------------------------------------------------
# Bi-objective: anchor solves + epsilon sweep
# --------------------------------------------------

# Anchor 1: minimize overtime cost (no unmet demand constraint) — the most unmet demand.
unmet_max = staffing_problem("hospital_staffing_cheapest", 0, "min_overtime")
# Anchor 2: minimize unmet demand (no overtime cost objective) — the best service.
unmet_min = staffing_problem("hospital_staffing_best_service", N_INTERIOR + 1, "min_unmet")

# Epsilon sweep: minimize overtime s.t. unmet <= eps, with eps spaced evenly over the
# anchors' unmet demand range, from most unmet (cheapest) to least (most expensive).
model.define(SweepPoint.new(index=std.common.range(1, N_INTERIOR + 1)))
model.define(SweepPoint.eps_unmet(
    unmet_max - SweepPoint.index * (unmet_max - unmet_min) / (N_INTERIOR + 1)
))
for i in range(1, N_INTERIOR + 1):
    staffing_problem(f"hospital_staffing_eps_{i}", i, "min_overtime", sweep_index=i)
