"""Underwriting report: reads the deployed commercial-underwriting model.

Run after `rai models deploy --path model`:
    python -m queries.underwriting_report

Prints the eligibility flags found at each level, the per-entity decline reasons
and marginal factors, the final risk-tier classification table, and the premium
by tier.
"""

from model import (
    ITV_THRESHOLD,
    MAX_FP_CLASS_FOR_ELIGIBILITY,
    MIN_YEAR_BUILT,
    Coverage,
    InsuredEntity,
    Location,
    Policy,
    RiskTier_Decline,
    RiskTier_NonStandard,
    RiskTier_Preferred,
    RiskTier_Standard,
    model,
)
from relationalai.semantics import sum

if __name__ == "__main__":
    print("=" * 70)
    print("Stage 1: Location- and coverage-level eligibility flags")
    print("=" * 70)

    poor_fp = model.where(Location.has_poor_fire_protection()).select(
        Location.id.alias("location_id"),
        Location.address.alias("address"),
        Location.fire_protection_class.alias("fp_class"),
    ).to_df()
    print(f"\nLocations with poor fire protection (FP > {MAX_FP_CLASS_FOR_ELIGIBILITY}): {len(poor_fp)}")
    if not poor_fp.empty:
        print(poor_fp.to_string(index=False))

    old_constr = model.where(Location.has_old_construction()).select(
        Location.id.alias("location_id"),
        Location.address.alias("address"),
        Location.year_built.alias("year_built"),
    ).to_df()
    print(f"\nLocations with old construction (year_built < {MIN_YEAR_BUILT}): {len(old_constr)}")
    if not old_constr.empty:
        print(old_constr.to_string(index=False))

    high_risk = model.where(Location.has_high_risk_occupancy()).select(
        Location.id.alias("location_id"),
        Location.address.alias("address"),
        Location.occupancy_class.alias("occupancy"),
    ).to_df()
    print(f"\nLocations with high-risk occupancy: {len(high_risk)}")
    if not high_risk.empty:
        print(high_risk.to_string(index=False))

    underinsured = model.where(Coverage.is_underinsured()).select(
        Coverage.id.alias("coverage_id"),
        Coverage.location.address.alias("location_address"),
        Coverage.coverage_limit.alias("limit"),
        Coverage.location.replacement_value.alias("replacement_value"),
    ).to_df()
    underinsured["itv_pct"] = (
        underinsured["limit"] / underinsured["replacement_value"] * 100
    ).round(1)
    print(f"\nUnderinsured BUILDING coverages (ITV < {int(ITV_THRESHOLD * 100)}%): {len(underinsured)}")
    if not underinsured.empty:
        print(underinsured.to_string(index=False))

    print("\n" + "=" * 70)
    print("Stage 2: Per-entity decline and marginal factors")
    print("=" * 70)


    def query_flag(rel, label):
        """Return a list of insured-entity IDs that match a unary boolean Relationship."""
        df = model.where(rel()).select(InsuredEntity.id.alias("id")).to_df()
        if df.empty:
            return set(), label
        return set(df["id"]), label


    decline_factor_rels = [
        (InsuredEntity.has_restricted_industry, "restricted_industry"),
        (InsuredEntity.has_insufficient_history, "insufficient_history"),
        (InsuredEntity.has_unprotected_location, "unprotected_location"),
        (InsuredEntity.has_old_construction_location, "old_construction_location"),
    ]
    marginal_factor_rels = [
        (InsuredEntity.has_marginal_industry, "marginal_industry"),
        (InsuredEntity.has_high_risk_occupancy_location, "high_risk_occupancy_location"),
        (InsuredEntity.has_underinsured_coverage, "underinsured_coverage"),
    ]

    ie_df = model.select(
        InsuredEntity.id.alias("id"),
        InsuredEntity.name.alias("name"),
        InsuredEntity.industry_code.alias("industry"),
        InsuredEntity.years_in_business.alias("years"),
    ).to_df().sort_values("id").reset_index(drop=True)

    for rel, label in decline_factor_rels + marginal_factor_rels:
        ids, _ = query_flag(rel, label)
        ie_df[label] = ie_df["id"].isin(ids)

    print("\nFlag matrix (True = flag set):")
    print(ie_df.to_string(index=False))

    print("\n" + "=" * 70)
    print("Stage 3: Risk-tier classification")
    print("=" * 70)

    decline_ids = set(
        model.where(RiskTier_Decline(InsuredEntity)).select(InsuredEntity.id.alias("id")).to_df()["id"]
    )
    nonstandard_ids = set(
        model.where(RiskTier_NonStandard(InsuredEntity)).select(InsuredEntity.id.alias("id")).to_df()["id"]
    )
    preferred_ids = set(
        model.where(RiskTier_Preferred(InsuredEntity)).select(InsuredEntity.id.alias("id")).to_df()["id"]
    )
    standard_ids = set(
        model.where(RiskTier_Standard(InsuredEntity)).select(InsuredEntity.id.alias("id")).to_df()["id"]
    )


    def classify(entity_id):
        if entity_id in decline_ids:
            return "DECLINE"
        if entity_id in nonstandard_ids:
            return "NON-STANDARD"
        if entity_id in preferred_ids:
            return "PREFERRED"
        if entity_id in standard_ids:
            return "STANDARD"
        return "UNCLASSIFIED"


    tier_df = ie_df[["id", "name", "industry", "years"]].copy()
    tier_df["tier"] = tier_df["id"].apply(classify)
    print("\nFinal risk tiers:")
    print(tier_df.to_string(index=False))

    # Sanity check: every entity must land in exactly one tier (mutual exclusivity).
    print("\nTier counts:")
    print(tier_df["tier"].value_counts().to_string())

    unclassified = tier_df[tier_df["tier"] == "UNCLASSIFIED"]
    if not unclassified.empty:
        raise SystemExit(f"{len(unclassified)} entities are unclassified: the rule set is non-exhaustive.")

    # Verify mutual exclusivity: no entity in two tiers.
    overlap = (decline_ids & nonstandard_ids) | (decline_ids & standard_ids) | (decline_ids & preferred_ids) \
        | (nonstandard_ids & standard_ids) | (nonstandard_ids & preferred_ids) | (standard_ids & preferred_ids)
    if overlap:
        raise SystemExit(f"{len(overlap)} entities classified into multiple tiers: {sorted(overlap)}")

    # Aggregate premium by tier — the underwriting business view.
    premium_df = model.where(Policy.insured_entity(InsuredEntity)).select(
        InsuredEntity.id.alias("id"),
        sum(Policy, Policy.total_premium).per(InsuredEntity).alias("premium"),
    ).to_df()
    tier_df = tier_df.merge(premium_df, on="id")
    print("\nPremium by tier:")
    print(tier_df.groupby("tier")["premium"].agg(["count", "sum", "mean"]).to_string())
