"""Load the sample catalog and feature rules, and check the catalog for the target region."""

from pathlib import Path

from pandas import read_csv

from .schema import Excludes, Implies, Option, Slot, model

TARGET_REGION = "EU"

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

slots_csv = read_csv(DATA_DIR / "slots.csv")
model.define(Slot.new(model.data(slots_csv).to_schema()))

options_csv = read_csv(DATA_DIR / "options.csv")
options_data = model.data(options_csv)
model.define(
    o := Option.new(id=options_data.id),
    o.name(options_data.name),
    o.price_cents(options_data.price_cents),
)
model.define(Option.slot(Slot)).where(
    Option.id(options_data.id),
    Slot.id(options_data.slot_id),
)

# Regional availability: an option is allowed in a region iff a row is present.
regional_csv = read_csv(DATA_DIR / "regional_rules.csv")
regional_data = model.data(regional_csv)
model.define(Option.allowed_in(regional_data.region)).where(
    Option.id(regional_data.option_id),
)

implies_csv = read_csv(DATA_DIR / "implies.csv")
model.define(Implies.new(model.data(implies_csv).to_schema()))

excludes_csv = read_csv(DATA_DIR / "excludes.csv")
model.define(Excludes.new(model.data(excludes_csv).to_schema()))

# --------------------------------------------------
# Validate the regional catalog against TARGET_REGION
# --------------------------------------------------

# The ICs in `model/reasoning.py` are scoped via `model.where(Option.allowed_in(TARGET_REGION), ...)`,
# which silently drops any IC whose options are not all region-allowed. The
# checks below catch the two failure modes that scoping hides; see the README
# troubleshooting blocks for the recovery steps.


def _validate_regional_catalog(slots_csv, options_csv, regional_csv, implies_csv, region):
    allowed_ids = {int(r["option_id"]) for _, r in regional_csv.iterrows() if r["region"] == region}
    slot_options: dict[int, list[int]] = {}
    for _, r in options_csv.iterrows():
        if int(r["id"]) in allowed_ids:
            slot_options.setdefault(int(r["slot_id"]), []).append(int(r["id"]))
    missing = [int(r["id"]) for _, r in slots_csv.iterrows() if int(r["id"]) not in slot_options]
    if missing:
        slot_names = {int(r["id"]): r["name"] for _, r in slots_csv.iterrows()}
        raise ValueError(
            f"No options are allowed in region {region!r} for slot(s) "
            f"{[slot_names[s] for s in missing]}. The exactly-one IC will not "
            "bind on those slots; every slot must have at least one "
            "region-allowed option."
        )
    dangling = [
        (int(r["head_id"]), int(r["tail_id"]))
        for _, r in implies_csv.iterrows()
        if int(r["head_id"]) in allowed_ids and int(r["tail_id"]) not in allowed_ids
    ]
    if dangling:
        option_names = {int(r["id"]): r["name"] for _, r in options_csv.iterrows()}
        rendered = ", ".join(f"{option_names[a]} -> {option_names[b]}" for a, b in dangling)
        raise ValueError(
            f"Region {region!r} has implies rules whose target option is "
            f"not allowed in the region: {rendered}. The implies IC will not "
            "bind on these rules; ban the head option in the region or "
            "allow the tail option."
        )


_validate_regional_catalog(slots_csv, options_csv, regional_csv, implies_csv, TARGET_REGION)
