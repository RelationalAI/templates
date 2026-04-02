"""Hospital Staffing (prescriptive optimization) template.

This template demonstrates **multi-objective optimization** via epsilon constraint
for a nurse scheduling problem with two competing objectives:

- **Primary**: Minimize overtime cost
- **Secondary**: Minimize unmet patient demand (service level)

Instead of bundling both into a single weighted objective
(overtime_cost + penalty × unmet_demand), the epsilon constraint method unbundles
them — sweeping the maximum allowed unmet demand from zero to the worst case.
This produces the **efficient frontier** showing exactly how much overtime cost
each level of patient service requires.

TRANSFORMATION FROM SINGLE-OBJECTIVE:
  The original template bundled two concerns into one objective:
    p.minimize(overtime_cost + PENALTY * sum(Shift.x_unmet_demand))
  The bi-objective version splits them:
    Primary:    p.minimize(overtime_cost)
    Secondary → constraint: p.satisfy(require(sum(Shift.x_unmet_demand) <= eps))
  This eliminates the arbitrary penalty weight and reveals the true tradeoff.
  The same "unbundle the penalty" pattern applies to any template that combines
  a primary cost with a penalty term (machine_maintenance, demand_planning,
  supply_chain_transport, supplier_reliability).

Run:
    `python hospital_staffing.py`

Output:
    Prints anchor solve results, Pareto frontier (cost vs service level),
    marginal analysis with knee detection, and allocation shifts.
"""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("hospital_staffing")
Concept, Property = model.Concept, model.Property

# --------------------------------------------------
# Define semantic model & load data
# --------------------------------------------------

data_dir = Path(__file__).parent / "data"

Nurse = Concept("Nurse", identify_by={"id": Integer})
Nurse.name = Property(f"{Nurse} has {String:name}")
Nurse.skill_level = Property(f"{Nurse} has {Integer:skill_level}")
Nurse.hourly_cost = Property(f"{Nurse} has {Float:hourly_cost}")
Nurse.regular_hours = Property(f"{Nurse} has {Integer:regular_hours}")
Nurse.overtime_multiplier = Property(f"{Nurse} has {Float:overtime_multiplier}")
Nurse.x_overtime_hours = Property(f"{Nurse} has {Float:overtime_hours}")
nurse_csv = read_csv(data_dir / "nurses.csv")
model.define(Nurse.new(model.data(nurse_csv).to_schema()))

Shift = Concept("Shift", identify_by={"id": Integer})
Shift.name = Property(f"{Shift} has {String:name}")
Shift.start_hour = Property(f"{Shift} has {Integer:start_hour}")
Shift.duration = Property(f"{Shift} has {Integer:duration}")
Shift.min_nurses = Property(f"{Shift} has {Integer:min_nurses}")
Shift.min_skill = Property(f"{Shift} has {Integer:min_skill}")
Shift.patient_demand = Property(f"{Shift} has {Integer:patient_demand}")
Shift.patients_per_nurse_hour = Property(f"{Shift} has {Float:patients_per_nurse_hour}")
Shift.x_patients_served = Property(f"{Shift} has {Float:patients_served}")
Shift.x_unmet_demand = Property(f"{Shift} has {Float:unmet_demand}")
shift_csv = read_csv(data_dir / "shifts.csv")
model.define(Shift.new(model.data(shift_csv).to_schema()))

Availability = Concept("Availability", identify_by={"nurse_id": Integer, "shift_id": Integer})
Availability.nurse = Property(f"{Availability} for {Nurse}")
Availability.shift = Property(f"{Availability} in {Shift}")
Availability.available = Property(f"{Availability} is {Integer:available}")

avail_csv = read_csv(data_dir / "availability.csv")
avail_data = model.data(avail_csv)
model.define(
    a := Availability.new(nurse_id=avail_data.nurse_id, shift_id=avail_data.shift_id),
    a.available(avail_data.available),
)
model.define(Availability.nurse(Nurse)).where(Availability.nurse_id == Nurse.id)
model.define(Availability.shift(Shift)).where(Availability.shift_id == Shift.id)

Assignment = Concept("Assignment", identify_by={"availability": Availability})
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")
model.define(Assignment.new(availability=Availability))

AssignmentRef = Assignment.ref()


# --------------------------------------------------
# Solve helper — shared constraints, parameterized objective
# --------------------------------------------------

def solve_staffing(objective="min_overtime", eps_unmet=None):
    """Solve the staffing problem with the given objective and optional epsilon constraint.

    objective: "min_overtime" (primary) or "min_unmet" (anchor 2 -- minimize unmet demand)
    eps_unmet: if set, add constraint sum(unmet) <= eps_unmet
    Returns (solve_info, variable_values_df, overtime_cost_value, total_unmet_value) or None if infeasible.
    """
    p = Problem(model, Float)

    p.solve_for(Assignment.x_assigned, type="bin", populate=False,
                name=["assigned", Assignment.availability.nurse.name,
                      Assignment.availability.shift.name])
    p.solve_for(Nurse.x_overtime_hours, type="cont", populate=False,
                name=["ot", Nurse.name], lower=0)
    p.solve_for(Shift.x_patients_served, type="cont", populate=False,
                name=["pt", Shift.name], lower=0)
    p.solve_for(Shift.x_unmet_demand, type="cont", populate=False,
                name=["ud", Shift.name], lower=0)

    # --- Constraints (same as original template) ---

    # Can only assign if available
    p.satisfy(model.require(Assignment.x_assigned <= Assignment.availability.available))

    # Every nurse works at least one shift
    nurse_shift_count = sum(AssignmentRef.x_assigned).where(
        AssignmentRef.availability.nurse == Nurse).per(Nurse)
    p.satisfy(model.require(nurse_shift_count >= 1))

    # Max 2 shifts per nurse
    p.satisfy(model.require(nurse_shift_count <= 2))

    # Minimum nurses per shift
    shift_staff_count = sum(AssignmentRef.x_assigned).where(
        AssignmentRef.availability.shift == Shift).per(Shift)
    p.satisfy(model.require(shift_staff_count >= Shift.min_nurses))

    # At least one nurse with required skill level per shift
    skilled_coverage = sum(AssignmentRef.x_assigned).where(
        AssignmentRef.availability.shift == Shift,
        AssignmentRef.availability.nurse.skill_level >= Shift.min_skill,
    ).per(Shift)
    p.satisfy(model.require(skilled_coverage >= 1))

    # Overtime >= total hours worked - regular hours
    total_hours_worked = sum(
        AssignmentRef.x_assigned * AssignmentRef.availability.shift.duration
    ).where(AssignmentRef.availability.nurse == Nurse).per(Nurse)
    p.satisfy(model.require(Nurse.x_overtime_hours >= total_hours_worked - Nurse.regular_hours))

    # Patients served <= demand per shift
    p.satisfy(model.require(Shift.x_patients_served <= Shift.patient_demand))

    # Patients served <= nursing capacity per shift
    shift_nursing_capacity = shift_staff_count * Shift.patients_per_nurse_hour * Shift.duration
    p.satisfy(model.require(Shift.x_patients_served <= shift_nursing_capacity))

    # Unmet demand >= patient demand - patients served
    p.satisfy(model.require(Shift.x_unmet_demand >= Shift.patient_demand - Shift.x_patients_served))

    # --- Epsilon constraint (if sweeping) ---
    # SINGLE-OBJECTIVE: unmet demand was penalized in the objective
    # BI-OBJECTIVE: unmet demand is bounded by epsilon
    if eps_unmet is not None:
        p.satisfy(model.require(sum(Shift.x_unmet_demand) <= eps_unmet))

    # --- Objective ---
    overtime_cost = sum(Nurse.x_overtime_hours * Nurse.hourly_cost * Nurse.overtime_multiplier)

    if objective == "min_overtime":
        p.minimize(overtime_cost)
    elif objective == "min_unmet":
        p.minimize(sum(Shift.x_unmet_demand))

    p.solve("highs", time_limit_sec=60)
    si = p.solve_info()

    if si.termination_status != "OPTIMAL":
        return None

    # Extract secondary objective values from variable_values df
    df = p.variable_values().to_df()

    # Compute unmet demand from df
    unmet_total = 0.0
    for _, row in df.iterrows():
        name = str(row.iloc[0])
        val = float(row.iloc[1])
        if name.startswith("ud_") and val > 1e-6:
            unmet_total += val

    if objective == "min_overtime":
        ot_cost_val = si.objective_value
        unmet_val = unmet_total
    else:
        ot_cost_val = None  # Not the objective; would need separate evaluation
        unmet_val = si.objective_value

    return si, df, ot_cost_val, unmet_val


# --------------------------------------------------
# Bi-objective: anchor solves + epsilon sweep
# --------------------------------------------------

if __name__ == "__main__":

    print("=" * 70)
    print("ANCHOR SOLVE 1: Minimize overtime cost (no unmet demand constraint)")
    print("=" * 70)
    result1 = solve_staffing("min_overtime", eps_unmet=None)
    if result1 is None:
        raise SystemExit("Anchor solve 1 (min overtime) is infeasible — check data and constraints.")
    si1, df1, ot1, unmet1 = result1
    print(f"Status: {si1.termination_status}")
    print(f"Overtime cost: ${ot1:.2f}")
    print(f"Unmet demand: {unmet1:.1f} patients")

    print(f"\n{'=' * 70}")
    print("ANCHOR SOLVE 2: Minimize unmet demand (no overtime cost objective)")
    print("=" * 70)
    result2 = solve_staffing("min_unmet", eps_unmet=None)
    if result2 is None:
        raise SystemExit("Anchor solve 2 (min unmet) is infeasible — check data and constraints.")
    si2, df2, _, unmet2 = result2
    print(f"Status: {si2.termination_status}")
    print(f"Min unmet demand: {unmet2:.1f} patients")

    # Feasible range: unmet demand goes from unmet2 (best service) to unmet1 (cheapest)
    unmet_min = unmet2  # best achievable service
    unmet_max = unmet1  # cheapest (most unmet demand)
    print(f"\nFeasible unmet demand range: [{unmet_min:.1f}, {unmet_max:.1f}]")

    # --------------------------------------------------
    # Epsilon sweep: minimize overtime s.t. unmet <= eps
    # --------------------------------------------------

    n_interior = 5
    epsilon_values = [
        unmet_max - i * (unmet_max - unmet_min) / (n_interior + 1)
        for i in range(1, n_interior + 1)
    ]
    # Sorted from most unmet (cheapest) to least unmet (most expensive)

    print(f"\n{'=' * 70}")
    print(f"EPSILON SWEEP: {n_interior} interior points")
    print(f"Unmet demand targets: {[f'{e:.1f}' for e in epsilon_values]}")
    print(f"{'=' * 70}")

    pareto = []
    pareto.append({
        "label": "cheapest",
        "eps_unmet": unmet_max,
        "overtime_cost": ot1,
        "unmet_demand": unmet1,
        "df": df1,
    })

    for i, eps in enumerate(epsilon_values):
        result = solve_staffing("min_overtime", eps_unmet=eps)
        if result is None:
            print(f"  Point {i+1} (unmet<={eps:.1f}): INFEASIBLE -- stopping")
            break

        si, df, ot_val, unmet_val = result
        pareto.append({
            "label": f"eps_{i+1}",
            "eps_unmet": eps,
            "overtime_cost": ot_val,
            "unmet_demand": unmet_val,
            "df": df,
        })
        print(f"  Point {i+1} (unmet<={eps:.1f}): overtime=${ot_val:.2f}, "
              f"actual_unmet={unmet_val:.1f}  [{si.termination_status}]")

    # Add best-service anchor
    result_best = solve_staffing("min_overtime", eps_unmet=unmet_min)
    if result_best is not None:
        si_best, df_best, ot_best, unmet_best = result_best
        pareto.append({
            "label": "best_service",
            "eps_unmet": unmet_min,
            "overtime_cost": ot_best,
            "unmet_demand": unmet_best,
            "df": df_best,
        })

    # --------------------------------------------------
    # Pareto analysis
    # --------------------------------------------------

    print(f"\n{'=' * 70}")
    print("EFFICIENT FRONTIER: Overtime Cost vs Patient Service")
    print(f"{'=' * 70}")
    print(f"{'#':>3} {'Label':>14} {'Unmet Demand':>14} {'Overtime Cost':>14}")
    print("-" * 48)
    for j, pt in enumerate(pareto):
        print(f"{j+1:>3} {pt['label']:>14} {pt['unmet_demand']:>14.1f} ${pt['overtime_cost']:>13.2f}")

    # ASCII Pareto plot: Overtime Cost (y) vs Unmet Demand (x)
    if len(pareto) >= 2:
        plot_h, plot_w = 12, 50
        unmets = [pt['unmet_demand'] for pt in pareto]
        costs = [pt['overtime_cost'] for pt in pareto]
        u_min, u_max = min(unmets), max(unmets)
        c_min, c_max = min(costs), max(costs)
        u_range = u_max - u_min if u_max > u_min else 1
        c_range = c_max - c_min if c_max > c_min else 1
        grid = [[" "] * plot_w for _ in range(plot_h)]
        for k, pt in enumerate(pareto):
            col = int((pt['unmet_demand'] - u_min) / u_range * (plot_w - 1))
            row = int((pt['overtime_cost'] - c_min) / c_range * (plot_h - 1))
            row = plot_h - 1 - row
            col = max(0, min(plot_w - 1, col))
            row = max(0, min(plot_h - 1, row))
            grid[row][col] = str(k + 1)
        print(f"\nOvertime Cost")
        for i, row in enumerate(grid):
            if i == 0:
                label = f"${c_max:>9,.2f}"
            elif i == plot_h - 1:
                label = f"${c_min:>9,.2f}"
            else:
                label = " " * 10
            print(f"{label} |{''.join(row)}|")
        print(f"{' ' * 10} +{'-' * plot_w}+")
        print(f"{' ' * 10}  {u_min:<.0f}{u_max:>{plot_w - len(f'{u_min:.0f}')},.0f} patients")
        print(f"{' ' * 10}  {'Unmet Demand':^{plot_w}}")

    # Marginal analysis
    if len(pareto) >= 3:
        print(f"\nMarginal analysis (cost of reducing unmet demand by 1 patient):")
        rates = []
        for j in range(len(pareto) - 1):
            d_cost = pareto[j+1]['overtime_cost'] - pareto[j]['overtime_cost']
            d_unmet = pareto[j]['unmet_demand'] - pareto[j+1]['unmet_demand']
            if abs(d_unmet) > 1e-6:
                rate = d_cost / d_unmet
                rates.append(rate)
                print(f"  {pareto[j]['label']:>14} → {pareto[j+1]['label']:<14}: "
                      f"Δcost=${d_cost:>+10.2f}, Δunmet={-d_unmet:>+6.1f}, "
                      f"marginal=${rate:>8.2f}/patient")
            else:
                rates.append(0)

        # Knee detection: rates[j+1]/rates[j] finds where marginal cost
        # per patient jumps most sharply (cost-per-patient is INCREASING
        # along the frontier, so the biggest jump ratio marks the knee).
        if len(rates) >= 2:
            max_jump = 0
            knee_idx = 1
            for j in range(len(rates) - 1):
                if rates[j] > 1e-6:
                    jump = rates[j+1] / rates[j]
                else:
                    jump = rates[j+1] if rates[j+1] > 0 else 0
                if jump > max_jump:
                    max_jump = jump
                    knee_idx = j + 1
            print(f"\n  Knee: Point {knee_idx + 1} ({pareto[knee_idx]['label']}) "
                  f"-- marginal cost jumps {max_jump:.1f}x beyond this point")
            print(f"  Recommendation: Target {pareto[knee_idx]['unmet_demand']:.0f} unmet patients "
                  f"at ${pareto[knee_idx]['overtime_cost']:.2f} overtime cost -- "
                  f"further service improvement costs significantly more per patient.")

            # Print nurse assignments at the knee point
            knee_df = pareto[knee_idx]["df"]
            assignments = []
            for _, row in knee_df.iterrows():
                vname = str(row.iloc[0])
                val = float(row.iloc[1])
                if vname.startswith("assigned_") and val > 0.5:
                    parts = vname.replace("assigned_", "").split("_", 1)
                    if len(parts) == 2:
                        assignments.append((parts[0], parts[1]))
            if assignments:
                print(f"\n  Knee-point assignments:")
                by_shift = {}
                for nurse, shift in assignments:
                    by_shift.setdefault(shift, []).append(nurse)
                for shift in sorted(by_shift):
                    nurses = ", ".join(sorted(by_shift[shift]))
                    print(f"    {shift}: {nurses}")
