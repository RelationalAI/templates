"""Machine Maintenance - Schedule preventive maintenance minimizing downtime cost."""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, data, define, require, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def define_model(config=None):
    """Define base model with Machine, TimeSlot, and Conflict concepts."""
    model = Model(f"machine_maintenance_{time_ns()}", config=config, use_lqp=False)

    # Concepts
    Machine = model.Concept("Machine")
    Machine.id = model.Property("{Machine} has {id:int}")
    Machine.name = model.Property("{Machine} has {name:string}")
    Machine.maintenance_hours = model.Property("{Machine} has {maintenance_hours:int}")
    Machine.failure_cost = model.Property("{Machine} has {failure_cost:float}")
    Machine.importance = model.Property("{Machine} has {importance:int}")

    TimeSlot = model.Concept("TimeSlot")
    TimeSlot.id = model.Property("{TimeSlot} has {id:int}")
    TimeSlot.day = model.Property("{TimeSlot} on {day:string}")
    TimeSlot.crew_hours = model.Property("{TimeSlot} has {crew_hours:int}")
    TimeSlot.cost_multiplier = model.Property("{TimeSlot} has {cost_multiplier:float}")

    Conflict = model.Concept("Conflict")
    Conflict.machine1 = model.Property("{Conflict} between {machine1:Machine}")
    Conflict.machine2 = model.Property("{Conflict} and {machine2:Machine}")

    # Load data
    data_dir = Path(__file__).parent / "data"

    machines_df = read_csv(data_dir / "machines.csv")
    data(machines_df).into(Machine, keys=["id"])

    slots_df = read_csv(data_dir / "time_slots.csv")
    data(slots_df).into(TimeSlot, keys=["id"])

    conflicts_df = read_csv(data_dir / "conflicts.csv")
    conflicts_data = data(conflicts_df)
    where(Machine.id(conflicts_data.machine1_id), (M2 := Machine.ref()).id(conflicts_data.machine2_id)).define(
        Conflict.new(machine1=Machine, machine2=M2)
    )

    # Schedule: decision variable for machine-to-slot assignment
    Schedule = model.Concept("Schedule")
    Schedule.machine = model.Property("{Schedule} for {machine:Machine}")
    Schedule.slot = model.Property("{Schedule} in {slot:TimeSlot}")
    Schedule.assigned = model.Property("{Schedule} is {assigned:float}")
    define(Schedule.new(machine=Machine, slot=TimeSlot))

    model.Machine, model.TimeSlot, model.Conflict, model.Schedule = Machine, TimeSlot, Conflict, Schedule
    return model


def define_problem(model):
    """Define decision variables, constraints, and objective."""
    s = SolverModel(model, "cont")
    Machine, TimeSlot, Conflict, Schedule = model.Machine, model.TimeSlot, model.Conflict, model.Schedule

    # Decision variable: binary assignment of machines to time slots
    s.solve_for(Schedule.assigned, type="bin", name=["x", Schedule.machine.name, Schedule.slot.day])

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
    total_cost = sum(Schedule.assigned * Schedule.machine.failure_cost * Schedule.slot.cost_multiplier)
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
