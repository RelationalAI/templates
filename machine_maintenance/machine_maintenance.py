"""Machine Maintenance - Schedule preventive maintenance minimizing downtime cost."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Machine, TimeSlot, and Conflict concepts."""
    model = Model(f"machine_maintenance_{time_ns()}", config=config, use_lqp=False)
    Concept, Property, Relationship = model.Concept, model.Property, model.Relationship

    data_dir = Path(__file__).parent / "data"

    # Machine: equipment requiring maintenance
    Machine = Concept("Machine")
    Machine.name = Property("{Machine} has name {name:String}")
    Machine.maintenance_hours = Property("{Machine} has maintenance_hours {maintenance_hours:int}")
    Machine.failure_cost = Property("{Machine} has failure_cost {failure_cost:float}")
    Machine.importance = Property("{Machine} has importance {importance:int}")
    machines_df = read_csv(data_dir / "machines.csv")
    data(machines_df).into(Machine, id="id", properties=["name", "maintenance_hours", "failure_cost", "importance"])

    # TimeSlot: available maintenance windows
    TimeSlot = Concept("TimeSlot")
    TimeSlot.day = Property("{TimeSlot} on day {day:String}")
    TimeSlot.crew_hours = Property("{TimeSlot} has crew_hours {crew_hours:int}")
    TimeSlot.cost_multiplier = Property("{TimeSlot} has cost_multiplier {cost_multiplier:float}")
    slots_df = read_csv(data_dir / "time_slots.csv")
    data(slots_df).into(TimeSlot, id="id", properties=["day", "crew_hours", "cost_multiplier"])

    # Conflict: machines that cannot be maintained simultaneously
    Conflict = Concept("Conflict")
    Conflict.machine1 = Relationship("{Conflict} between {machine1:Machine}")
    Conflict.machine2 = Relationship("{Conflict} and {machine2:Machine}")
    conflicts_df = read_csv(data_dir / "conflicts.csv")
    data(conflicts_df).into(
        Conflict,
        keys=["machine1_id", "machine2_id"],
        relationships={"machine1": ("machine1_id", Machine), "machine2": ("machine2_id", Machine)},
    )

    # Schedule: decision variable for machine-to-slot assignment
    Schedule = Concept("Schedule")
    Schedule.machine = Relationship("{Schedule} for {machine:Machine}")
    Schedule.slot = Relationship("{Schedule} in {slot:TimeSlot}")
    Schedule.assigned = Property("{Schedule} is assigned {assigned:float}")
    define(Schedule.new(machine=Machine, slot=TimeSlot))

    model.Machine, model.TimeSlot, model.Conflict, model.Schedule = Machine, TimeSlot, Conflict, Schedule
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Machine, TimeSlot, Conflict, Schedule = model.Machine, model.TimeSlot, model.Conflict, model.Schedule

    # Decision variable: binary assignment of machines to time slots
    s.solve_for(Schedule.assigned, type="bin", name=[Schedule.machine, Schedule.slot])

    # Constraint: each machine scheduled exactly once
    Sch = Schedule.ref()
    machine_scheduled = sum(Sch.assigned).where(Sch.machine == Machine).per(Machine)
    s.satisfy(require(machine_scheduled == 1))

    # Constraint: crew hours per slot not exceeded
    slot_hours = sum(Sch.assigned * Sch.machine.maintenance_hours).where(Sch.slot == TimeSlot).per(TimeSlot)
    s.satisfy(require(slot_hours <= TimeSlot.crew_hours))

    # Constraint: conflicting machines cannot be scheduled in same slot
    Sch1 = Schedule.ref()
    Sch2 = Schedule.ref()
    s.satisfy(
        require(Sch1.assigned + Sch2.assigned <= 1).where(
            Sch1.machine == Conflict.machine1,
            Sch2.machine == Conflict.machine2,
            Sch1.slot == Sch2.slot,
        )
    )

    # Objective: minimize total maintenance cost (base cost * slot multiplier)
    # Higher importance machines have higher implicit priority via failure_cost
    total_cost = sum(
        Schedule.assigned * Schedule.machine.failure_cost * Schedule.slot.cost_multiplier
    )
    s.minimize(total_cost)

    return s


def solve(config=None, solver_name="highs"):
    """Orchestrate model, problem, and solver execution."""
    model = define_model(config)
    solver_model = define_problem(model)
    solver = Solver(solver_name)
    solver_model.solve(solver, time_limit_sec=60)
    return solver_model


def extract_solution(solver_model):
    """Extract solution as dict with metadata."""
    return {
        "status": solver_model.termination_status,
        "objective": solver_model.objective_value,
        "variables": solver_model.variable_values().to_df(),
    }


if __name__ == "__main__":
    sm = solve()
    sol = extract_solution(sm)

    print(f"Status: {sol['status']}")
    print(f"Total maintenance cost: ${sol['objective']:.2f}")
    print("\nMaintenance schedule:")
    df = sol["variables"]
    active = df[df["float"] > 0.5] if "float" in df.columns else df
    print(active.to_string(index=False))
