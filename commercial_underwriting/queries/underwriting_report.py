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
    RiskTier_Decline,
    RiskTier_NonStandard,
    RiskTier_Preferred,
    RiskTier_Standard,
    TierPremium,
    model,
)
from pandas import Index

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
        Coverage.insurance_to_value.alias("itv"),
    ).to_df()
    underinsured["itv_pct"] = (underinsured.pop("itv") * 100).round(1)
    print(f"\nUnderinsured BUILDING coverages (ITV < {int(ITV_THRESHOLD * 100)}%): {len(underinsured)}")
    if not underinsured.empty:
        print(underinsured.to_string(index=False))

    print("\n" + "=" * 70)
    print("Stage 2: Per-entity decline and marginal factors")
    print("=" * 70)


    def query_flag(rel):
        """Return the set of insured-entity IDs that match a unary boolean Relationship."""
        df = model.where(rel()).select(InsuredEntity.id.alias("id")).to_df()
        return set(df["id"])


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
        ie_df[label] = ie_df["id"].isin(query_flag(rel))

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

    tier_labels = model.select(
        InsuredEntity.id.alias("id"), InsuredEntity.tier.alias("tier")
    ).to_df()
    tier_df = ie_df[["id", "name", "industry", "years"]].merge(tier_labels, on="id", how="left")
    print("\nFinal risk tiers:")
    print(tier_df.to_string(index=False))

    # Per-tier insured counts and premium, as the model publishes them.
    tier_premium = model.select(
        TierPremium.tier.alias("tier"),
        TierPremium.n_insureds.alias("count"),
        TierPremium.total_premium.alias("sum"),
        TierPremium.mean_premium.alias("mean"),
    ).to_df().set_index("tier").sort_index()

    # Sanity check: every entity must land in exactly one tier (mutual exclusivity).
    # Most insureds first; equal counts keep the order the tiers first appear above.
    print("\nTier counts:")
    first_seen = Index(tier_df["tier"].drop_duplicates(), name="tier")
    print(
        tier_premium["count"].reindex(first_seen).sort_values(ascending=False, kind="stable")
        .to_string()
    )

    unclassified = tier_df[tier_df["tier"] == "UNCLASSIFIED"]
    if not unclassified.empty:
        print(f"\nWARNING: {len(unclassified)} entities are unclassified — rule set is non-exhaustive.")

    # Verify mutual exclusivity: no entity in two tiers.
    overlap = (decline_ids & nonstandard_ids) | (decline_ids & standard_ids) | (decline_ids & preferred_ids) \
        | (nonstandard_ids & standard_ids) | (nonstandard_ids & preferred_ids) | (standard_ids & preferred_ids)
    if overlap:
        print(f"\nWARNING: {len(overlap)} entities classified into multiple tiers: {sorted(overlap)}")

    # Premium by tier — the underwriting business view. Premium is per insured, summed
    # over its policies; an insured without a policy counts in its tier with zero premium.
    print("\nPremium by tier:")
    print(tier_premium.to_string())
