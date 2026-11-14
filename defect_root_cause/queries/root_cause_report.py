"""Root-cause report: reads the deployed defect-diagnosis model.

Run after `rai models deploy --path model`:
    python -m queries.root_cause_report

Prints per-stage diagnostics -- genealogy reachability validation, the
contrast-scored suspect factors with lift, the solve's termination status, and the
DiagnosisResult headline (defective units, units explained, coverage) with the
ranked root-cause factors, each with corroborating evidence.
"""

from model import (
    LIFT_THRESHOLD,
    MIN_DEFECTS,
    MIN_SUPPORT,
    DiagnosisCost,
    DiagnosisResult,
    Factor,
    Lot,
    Machine,
    PlantBaseline,
    SolveStatus,
    Supplier,
    Unit,
    cover,
    model,
    num_cons,
    num_edges,
    num_min_objs,
    num_nodes,
    num_vars,
)

if __name__ == "__main__":
    n_units = model.select(Unit.id).to_df()
    n_def = model.where(Unit.is_defective()).select(Unit.id).to_df()
    print(
        f"Loaded {len(n_units)} units, {len(n_def)} defective ({len(n_def) / len(n_units):.2%} final-test failure rate)"
    )

    # Descriptive: when did the spike start? A real investigation begins on the
    # timeline -- failures by build week -- before touching genealogy. The onset is
    # the first week whose rate runs well above the opening week's baseline; it
    # tells the rest of the chain which window's changes to interrogate.
    wk = model.select(
        Unit.build_week.alias("week"), Unit.defective.alias("defective")
    ).to_df()
    wk["defective"] = wk["defective"].astype(int)
    timeline = wk.groupby("week").agg(
        units=("defective", "size"), defects=("defective", "sum")
    )
    timeline["rate"] = timeline["defects"] / timeline["units"]
    opening = timeline["rate"].iloc[0]
    onset = next((int(w) for w, r in timeline["rate"].items() if r > 2 * opening), None)
    print("\nWhen did the spike start? Final-test failure rate by build week:")
    for week, r in timeline.iterrows():
        mark = "  <- spike onset" if onset == int(week) else ""
        print(
            f"  week {int(week)}: {int(r['units']):>4} units   {r['rate']:>5.1%}{mark}"
        )
    print(
        f"Spike onset at week {onset}: the chain interrogates what entered the line then."
    )

    n_nodes = int(model.select(num_nodes.alias("n")).to_df()["n"].iloc[0])
    n_edges = int(model.select(num_edges.alias("n")).to_df()["n"].iloc[0])
    print(f"\nGenealogy graph: {n_nodes} lot nodes, {n_edges} parent->child edges")

    # Naive view: rank candidate factors by the raw count of defective units they
    # touch. High-volume factors dominate -- a near-universal housing lot and the
    # busiest placement line top the list purely because they touch almost
    # everything. That is exactly the trap the contrast stage corrects. Genealogy
    # closure puts lots and machines on the same footing: a deep lot is "touched by"
    # every finished unit that carries it.
    incidence = (
        model.where((f := Factor.ref()).touches(u := Unit.ref()))
        .select(
            f.id.alias("factor"), f.kind.alias("kind"), u.defective.alias("defective")
        )
        .to_df()
    )
    incidence["defective"] = incidence["defective"].astype(int)
    top_raw = (
        incidence.groupby(["factor", "kind"])
        .agg(units=("defective", "size"), defects=("defective", "sum"))
        .reset_index()
        .sort_values("defects", ascending=False)
        .head(6)
        .reset_index(drop=True)
    )
    print(
        f"\nBackward reachability built {len(incidence):,} (factor, unit) incidence facts."
    )
    print(
        "Top candidate factors by RAW defective units touched (pre-contrast -- note the high-volume bias):"
    )
    print(top_raw.to_string(index=False))

    suspects = (
        model.where(Factor.is_suspect(f := Factor.ref()))
        .select(
            f.id.alias("factor"),
            f.kind.alias("kind"),
            f.touched_count.alias("units"),
            f.defect_count.alias("defects"),
            f.defect_rate.alias("rate"),
            f.lift.alias("lift"),
        )
        .to_df()
        .sort_values("lift", ascending=False)
        .reset_index(drop=True)
    )
    baseline_rate = float(model.select(PlantBaseline.failure_rate).to_df().iloc[0, 0])
    print(
        f"\nContrast scoring: {len(suspects)} suspect factors (baseline failure rate {baseline_rate:.2%}, "
        f"lift>={LIFT_THRESHOLD}, support>={MIN_SUPPORT}, defects>={MIN_DEFECTS})"
    )
    print(suspects.to_string(index=False))

    # Formulation audit: variables and objective registered, and -- the easy thing to
    # get wrong -- one coverage constraint grounded per defective unit.
    n_vars = model.select(num_vars).to_df().iloc[:, 0].tolist()
    n_cons = model.select(num_cons).to_df().iloc[:, 0].tolist()
    n_objs = model.select(num_min_objs).to_df().iloc[:, 0].tolist()
    if not n_vars or n_vars[0] <= 0:
        raise SystemExit(f"no variables: {n_vars}")
    if not n_cons or n_cons[0] <= 0:
        raise SystemExit(f"no constraints: {n_cons}")
    if n_objs != [1]:
        raise SystemExit(f"expected one minimization objective, got {n_objs}")
    n_cover = len(model.select(cover).to_df())
    if n_cover != len(n_def):
        raise SystemExit(f"coverage grounded {n_cover} rows, expected {len(n_def)}")
    print(
        f"\nFormulation audit: {n_cover} coverage constraints grounded (one per defective unit)."
    )

    # Status and objective of the latest refresh's solve.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    cost = model.select(DiagnosisCost).to_df().iloc[:, 0].tolist()
    print(
        f"\nDiagnosis solve: {', '.join(status)}   objective={round(cost[0], 9) if cost else None}"
    )
    if status != ["OPTIMAL"]:
        raise SystemExit(f"No optimal diagnosis: termination status {status}")

    # Read back the diagnosis (populate=True writes the solution onto is_root_cause).
    diagnosis = (
        model.where((f := Factor.ref()).is_root_cause > 0.5)
        .select(
            f.id.alias("factor"),
            f.label.alias("label"),
            f.kind.alias("kind"),
            f.defect_count.alias("defects_on_factor"),
            f.lift.alias("lift"),
        )
        .to_df()
        .sort_values("lift", ascending=False)
        .reset_index(drop=True)
    )

    # The headline, read back from the DiagnosisResult singleton.
    headline = model.select(
        DiagnosisResult.n_defective.alias("n_defective"),
        DiagnosisResult.n_explained.alias("n_explained"),
        DiagnosisResult.n_root_causes.alias("n_root_causes"),
        DiagnosisResult.coverage.alias("coverage"),
    ).to_df()
    n_defective = int(headline["n_defective"].iloc[0])
    n_explained = int(headline["n_explained"].iloc[0])
    print(
        f"\nRoot-cause diagnosis: {int(headline['n_root_causes'].iloc[0])} factors explain {n_explained}/{n_defective} "
        f"defective units ({headline['coverage'].iloc[0]:.0%} coverage)"
    )
    print(diagnosis.to_string(index=False))

    # Corroborating evidence per named cause, the way a real RCA write-up reads:
    # the defect signature it concentrates (a paste fault should present as cold
    # solder, a reflow fault as solder bridging), plus a kind-specific tell --
    # supplier and receipt date for a lot, calibration age for a machine. All of it
    # is read back from ontology already loaded; the diagnosis is the hypothesis,
    # this is the supporting evidence an engineer would confirm physically.
    sig = (
        model.where(
            (f := Factor.ref()).is_root_cause > 0.5,
            f.touches(u := Unit.ref()),
            u.is_defective(),
        )
        .select(f.id.alias("factor"), u.defect_type.alias("defect_type"))
        .to_df()
    )
    print("\nCorroborating evidence per root cause:")
    for _, row in diagnosis.iterrows():
        fid, kind, label = row["factor"], row["kind"], row["label"]
        types = sig[sig["factor"] == fid]["defect_type"]
        dom = types.value_counts()
        signature = f"{dom.iloc[0] / len(types):.0%} {dom.index[0]}"
        ref = fid.split("::", 1)[1]
        if kind == "LOT":
            tell_df = (
                model.where(
                    (lo := Lot.ref()).id == ref, lo.supplier(sp := Supplier.ref())
                )
                .select(sp.name.alias("supplier"), lo.received_date.alias("recv"))
                .to_df()
            )
            tell = f"supplier {tell_df['supplier'].iloc[0]}, received {tell_df['recv'].iloc[0]}"
        else:
            tell_df = (
                model.where((mm := Machine.ref()).id == ref)
                .select(mm.calibration_age_days.alias("age"))
                .to_df()
            )
            tell = f"{int(tell_df['age'].iloc[0])} days since last calibration"
        print(f"  {label:<26} {signature:<18} {tell}")
