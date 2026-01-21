"""Shift Assignment - Find valid worker-shift assignments using constraint satisfaction.

This template demonstrates the HOLISTIC pattern where the solver is one part
of a larger pyrel workflow:

    Pre-solve derivation (pyrel rules)
        ↓
    Solver model (optimization)
        ↓
    Post-solve processing (pyrel rules)
        ↓
    Final output

Key patterns shown:
- Pre-solve: Derive facts that feed into solver constraints
- Solver: CSP with binary variables
- Post-solve: Convert numeric solution to boolean relations, compute summaries
- Auxiliary vs meaningful variables: Only export what has business meaning
"""

from pathlib import Path
from time import time_ns

from pandas import read_csv
from relationalai.semantics import Model, count, data, define, require, select, sum, where
from relationalai.semantics.reasoners.optimization import Solver, SolverModel


def solve(config=None, solver_name="minizinc", min_coverage=2, max_shifts_per_worker=1):
    """
    Build and solve the shift assignment problem.

    Returns solver_model with model and concepts attached for solution access.
    """
    # =========================================================================
    # 1. Create model and load data
    # =========================================================================
    model = Model(f"shift_assignment_{time_ns()}", config=config, use_lqp=False)

    Worker = model.Concept("Worker")
    Worker.id = model.Property("{Worker} has {id:int}")
    Worker.name = model.Property("{Worker} has {name:string}")

    Shift = model.Concept("Shift")
    Shift.id = model.Property("{Shift} has {id:int}")
    Shift.name = model.Property("{Shift} has {name:string}")

    Assignment = model.Concept("Assignment")
    Assignment.worker = model.Property("{Assignment} has {worker:Worker}")
    Assignment.shift = model.Property("{Assignment} has {shift:Shift}")

    data_dir = Path(__file__).parent / "data"
    data(read_csv(data_dir / "workers.csv")).into(Worker, keys=["id"])
    data(read_csv(data_dir / "shifts.csv")).into(Shift, keys=["id"])

    # Create assignments only for available worker-shift pairs
    avail = data(read_csv(data_dir / "availability.csv"))
    where(
        Worker.id(avail.worker_id),
        Shift.id(avail.shift_id)
    ).define(
        Assignment.new(worker=Worker, shift=Shift)
    )

    # =========================================================================
    # 2. PRE-SOLVE DERIVATION (pyrel rules that feed into solver)
    # =========================================================================
    # These derived facts inform constraints and can be used for reporting.

    # How many workers are available for each shift?
    Shift.available_workers = model.Property("{Shift} has {available_workers:int}")
    Asn = Assignment.ref()
    define(
        Shift.available_workers(count(Asn).where(Asn.shift == Shift).per(Shift))
    )

    # How flexible is each worker? (number of shifts they can work)
    Worker.flexibility = model.Property("{Worker} has {flexibility:int}")
    Asn2 = Assignment.ref()
    define(
        Worker.flexibility(count(Asn2).where(Asn2.worker == Worker).per(Worker))
    )

    # =========================================================================
    # 3. Define decision variable (will be populated by solver)
    # =========================================================================
    # This is the solver's output - an integer (0 or 1) for each assignment
    Assignment.assigned = model.Property("{Assignment} assigned {assigned:int}")

    # =========================================================================
    # 4. Build constraint satisfaction problem
    # =========================================================================
    s = SolverModel(model, "int")

    # Decision variable: binary (0 or 1)
    s.solve_for(
        Assignment.assigned,
        name=["x", Assignment.worker.name, Assignment.shift.name],
        type="int"
    )
    s.satisfy(require(Assignment.assigned >= 0, Assignment.assigned <= 1))

    # Constraint: each worker works at most max_shifts_per_worker shifts
    Asn3 = Assignment.ref()
    worker_shifts = sum(Asn3.assigned).where(Asn3.worker == Worker).per(Worker)
    s.satisfy(require(worker_shifts <= max_shifts_per_worker))

    # Constraint: each shift needs minimum coverage
    Asn4 = Assignment.ref()
    shift_coverage = sum(Asn4.assigned).where(Asn4.shift == Shift).per(Shift)
    s.satisfy(require(shift_coverage >= min_coverage))

    # =========================================================================
    # 5. Solve
    # =========================================================================
    solver = Solver(solver_name)
    s.solve(solver, time_limit_sec=60)

    # =========================================================================
    # 6. POST-SOLVE PROCESSING (pyrel rules consuming solver output)
    # =========================================================================
    # Convert solver's numeric output to clean boolean relations.
    # MILP/CSP solvers return floats (e.g., 0.9999 instead of 1).
    # Define derived relations that threshold the numeric values.

    # Boolean relation: is this assignment active?
    # Use a boolean property and define it conditionally
    Assignment.is_assigned = model.Property("{Assignment} has {is_assigned:bool}")
    define(Assignment.is_assigned(True)).where(Assignment.assigned >= 1)

    # Compute actual coverage per shift (from solution)
    Shift.actual_coverage = model.Property("{Shift} has {actual_coverage:int}")
    Asn5 = Assignment.ref()
    define(
        Shift.actual_coverage(
            count(Asn5).where(Asn5.shift == Shift, Asn5.is_assigned(True)).per(Shift)
        )
    )

    # Compute assignments per worker (from solution)
    Worker.assigned_shifts = model.Property("{Worker} has {assigned_shifts:int}")
    Asn6 = Assignment.ref()
    define(
        Worker.assigned_shifts(
            count(Asn6).where(Asn6.worker == Worker, Asn6.is_assigned(True)).per(Worker)
        )
    )

    # =========================================================================
    # 7. Attach references for solution access
    # =========================================================================
    s.model = model
    s.Worker = Worker
    s.Shift = Shift
    s.Assignment = Assignment

    return s


# =============================================================================
# Backward compatibility
# =============================================================================

def extract_solution(solver_model):
    """Extract solution - prefer querying relations directly (see __main__)."""
    if hasattr(solver_model, 'Assignment'):
        Assignment = solver_model.Assignment
        solution_df = select(
            Assignment.worker.name.alias("worker"),
            Assignment.shift.name.alias("shift")
        ).where(Assignment.is_assigned(True)).to_df()
        return {
            "status": solver_model.termination_status,
            "objective": None,
            "assignments": solution_df,
        }
    else:
        return {
            "status": solver_model.termination_status,
            "objective": None,
            "variables": solver_model.variable_values().to_df(),
        }


if __name__ == "__main__":
    solver_model = solve(min_coverage=2)
    print(f"Status: {solver_model.termination_status}")

    Worker = solver_model.Worker
    Shift = solver_model.Shift
    Assignment = solver_model.Assignment

    # =========================================================================
    # PRE-SOLVE DERIVED FACTS (computed before solver ran)
    # =========================================================================
    print("\n" + "="*60)
    print("PRE-SOLVE ANALYSIS (derived facts that informed constraints)")
    print("="*60)

    print("\nShift availability (workers available per shift):")
    shift_avail = select(Shift.name, Shift.available_workers).to_df()
    print(shift_avail.to_string(index=False))

    print("\nWorker flexibility (shifts each worker can work):")
    worker_flex = select(Worker.name, Worker.flexibility).to_df()
    print(worker_flex.to_string(index=False))

    # =========================================================================
    # SOLUTION (meaningful relations only - not auxiliary variables)
    # =========================================================================
    print("\n" + "="*60)
    print("SOLUTION (via post-processed boolean relation)")
    print("="*60)

    # Query the clean boolean relation - this is what matters for business
    assignments = select(
        Assignment.worker.name.alias("worker"),
        Assignment.shift.name.alias("shift")
    ).where(Assignment.is_assigned(True)).to_df()
    print("\nFinal assignments:")
    print(assignments.to_string(index=False))

    # =========================================================================
    # POST-SOLVE SUMMARIES (derived from solution)
    # =========================================================================
    print("\n" + "="*60)
    print("POST-SOLVE SUMMARIES (derived from solution)")
    print("="*60)

    print("\nActual coverage per shift:")
    coverage = select(Shift.name, Shift.actual_coverage).to_df()
    print(coverage.to_string(index=False))

    print("\nAssignments per worker:")
    worker_assignments = select(Worker.name, Worker.assigned_shifts).to_df()
    # Only show workers who got assigned (cast to int for comparison)
    worker_assignments["assigned_shifts"] = worker_assignments["assigned_shifts"].astype(int)
    assigned_workers = worker_assignments[worker_assignments["assigned_shifts"] > 0]
    print(assigned_workers.to_string(index=False))

    # =========================================================================
    # RAW SOLVER OUTPUT (for debugging - includes auxiliary numeric values)
    # =========================================================================
    print("\n" + "="*60)
    print("RAW SOLVER OUTPUT (for debugging)")
    print("="*60)
    raw = select(
        Assignment.worker.name.alias("worker"),
        Assignment.shift.name.alias("shift"),
        Assignment.assigned
    ).to_df()
    print(raw.to_string(index=False))
