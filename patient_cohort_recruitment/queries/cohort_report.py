"""Patient cohort report: reads the deployed patient_cohort_recruitment model.

Run `python -m queries.cohort_report` after `rai models deploy --path model`. Prints the
solve status, the kinase-pathway gene closure, the eligible patient set,
the chosen cohort, and the per-axis coverage tally.
"""

from model import (
    CoverableAdverseEvent,
    CoverableGene,
    CoverableTherapy,
    EligiblePatient,
    KinaseGene,
    SolveStatus,
    model,
)

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")

    print("\nKinase-pathway gene closure (reachable from KINASE_ROOT_GENE_ID):")
    model.select(
        KinaseGene.id.alias("gene_id"),
        KinaseGene.name.alias("gene_name"),
    ).inspect()

    print("\nEligible patients (carry a kinase mutation and have a qualifying pair):")
    model.select(
        EligiblePatient.id.alias("patient_id"),
        EligiblePatient.name.alias("patient_name"),
    ).inspect()

    print("\nSelected cohort:")
    model.select(
        EligiblePatient.id.alias("patient_id"),
        EligiblePatient.name.alias("patient_name"),
        EligiblePatient.age_years.alias("age_years"),
    ).where(EligiblePatient.is_in_cohort == 1).inspect()

    print("\nKinase-pathway genes covered by the cohort:")
    model.select(
        CoverableGene.id.alias("gene_id"),
        CoverableGene.name.alias("gene_name"),
    ).where(CoverableGene.is_covered == 1).inspect()

    print("\nTherapies covered by the cohort:")
    model.select(
        CoverableTherapy.id.alias("therapy_id"),
        CoverableTherapy.name.alias("therapy_name"),
    ).where(CoverableTherapy.is_covered == 1).inspect()

    print("\nAdverse events covered by the cohort:")
    model.select(
        CoverableAdverseEvent.id.alias("ae_id"),
        CoverableAdverseEvent.term.alias("ae_term"),
    ).where(CoverableAdverseEvent.is_covered == 1).inspect()
