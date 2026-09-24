"""Build the golden fixtures F1-F5 (CSV per contract table + expected.yaml) from the papers' examples.

    python -m data.fixtures.build_fixtures

Every expected value below is derived by hand from the paper text; comments show the arithmetic.
F2 and F3 are reconstructed so the papers' TEXT claims hold with valid share totals (the figures
are only partly legible) — see PLAN.md §2.2.
"""

from pathlib import Path

import pandas as pd
import yaml
from model.contracts import CONTRACTS, write_dir

HERE = Path(__file__).resolve().parent


def companies(ids, banks=()):
    return pd.DataFrame([{
        "eid": c, "name": c.split(":")[1].replace("_", " ").title(), "legal_form": "SPA",
        "sector": "BANKING" if c in banks else "HOLDING", "province": "PR00",
        "inc_date": "2001-01-01", "is_bank": int(c in banks),
    } for c in ids])


def persons(specs):
    """specs: {eid: dict(overrides)}; defaults give distinct, unrelated-looking people."""
    rows = []
    for i, (eid, o) in enumerate(specs.items(), start=1):
        by = o.get("birth_year", 1960 + 3 * i)
        rows.append({
            "eid": eid, "num": i, "first_name": o.get("first_name", f"Name{i}"),
            "surname": o.get("surname", f"Surname{i}"), "sex": o.get("sex", "M"),
            "birth_date": f"{by}-06-15", "birth_year": by, "birth_city": o.get("birth_city", f"City{i}"),
            "address": o.get("address", f"{i} Via Uno"), "province": o.get("province", f"PR{i:02d}"),
            "is_pep": o.get("is_pep", 0), "has_record": o.get("has_record", 0),
        })
    return pd.DataFrame(rows)


def holdings(edges):
    rows = [{"owner_eid": a, "owned_eid": b, "share": w, "right_type": "ownership"} for a, b, w in edges]
    return pd.DataFrame(rows, columns=list(CONTRACTS["shareholdings"])).astype({"share": float})


def links(pairs):
    return pd.DataFrame([{"a_eid": a, "b_eid": b, "link_type": t, "source": "registry"} for a, b, t in pairs])


def empty(name):
    return pd.DataFrame({c: pd.Series(dtype="object") for c in CONTRACTS[name]})


def ents(edges):
    ids = {e for a, b, _ in edges for e in (a, b)}
    return sorted(i for i in ids if i.startswith("C:")), sorted(i for i in ids if i.startswith("P:"))


def save(name, tables, expected):
    d = HERE / name
    write_dir(tables, d)
    (d / "expected.yaml").write_text(yaml.safe_dump(expected, sort_keys=False))
    print(f"wrote {d.relative_to(HERE.parents[1])} ({', '.join(tables)})")


# ---------------------------------------------------------------- F1: P1 Figure 1 (Weaving, EDBT 2020)
F1_EDGES = [
    ("P:P1", "C:C", 0.8), ("C:C", "C:D", 0.75), ("C:D", "C:E", 0.4), ("C:D", "C:F", 0.2),
    ("C:E", "C:F", 0.4), ("P:P1", "C:E", 0.2), ("C:F", "C:L", 0.2), ("P:P2", "C:G", 0.6),
    ("C:G", "C:H", 0.6), ("C:H", "C:L", 0.4), ("C:H", "C:I", 0.1), ("P:P2", "C:I", 0.5),
]


def f1():
    comps, pers = ents(F1_EDGES)
    save("f1_weaving_fig1", {
        "companies": companies(comps),
        "persons": persons({p: {} for p in pers}),
        "shareholdings": holdings(F1_EDGES),
        "family_links_known": links([("P:P1", "P:P2", "PARTNER_OF")]),
    }, {
        "controls": [["P:P1", "C:C"], ["P:P1", "C:D"], ["P:P1", "C:E"], ["P:P1", "C:F"],
                     ["P:P2", "C:G"], ["P:P2", "C:H"], ["P:P2", "C:I"], ["C:C", "C:D"], ["C:G", "C:H"]],
        "not_controls": [["P:P1", "C:L"], ["P:P2", "C:L"], ["C:C", "C:E"], ["C:D", "C:F"]],
        # first layer at which control appears: D via C (1); E = 0.4 via D + 0.2 own (2); F = 0.2 via D + 0.4 via E (3)
        "control_depth": {"P:P1|C:C": 0, "P:P1|C:D": 1, "P:P1|C:E": 2, "P:P1|C:F": 3, "P:P2|C:I": 2},
        "control_steps": {"P:P1|C:F": [["C:D", 0.2], ["C:E", 0.4]]},
        # P1->D = 0.8*0.75; P2->I = 0.5 + 0.6*0.6*0.1; P1->F = .8*.75*.2 + .8*.75*.4*.4 + .2*.4
        "phi": {"P:P1|C:D": 0.6, "P:P2|C:I": 0.536, "P:P1|C:F": 0.296},
        "close_links": [["C:C", "C:D"], ["C:C", "C:E"], ["C:C", "C:F"], ["C:D", "C:E"], ["C:D", "C:F"],
                        ["C:E", "C:F"], ["C:F", "C:L"], ["C:G", "C:H"], ["C:G", "C:I"], ["C:H", "C:I"],
                        ["C:G", "C:L"], ["C:H", "C:L"]],
        "families": [["P:P1", "P:P2"]],
        "family_controls": [{"members": ["P:P1", "P:P2"], "company": "C:L"}],   # 0.2 via F + 0.4 via H
        "family_close_links_contains": [["C:D", "C:G"]],
        "family_close_links_count": 12,                                          # {C,D,E,F} x {G,H,I}
    })


# ---------------------------------------------------------------- F2: P1 Figure 2 / P2 Figure 1 (reconstructed)
F2_EDGES = [
    ("P:P1", "C:C4", 0.8), ("P:P1", "C:C7", 0.1), ("C:C4", "C:C5", 0.4), ("C:C4", "C:C7", 0.12),
    ("C:C5", "C:C7", 0.2), ("P:P2", "C:C5", 0.6), ("P:P2", "C:C6", 0.51), ("P:P2", "C:C8", 0.1),
    ("C:C6", "C:C7", 0.4), ("C:C6", "C:C6", 0.09), ("P:P3", "C:C6", 0.4), ("P:P3", "C:C8", 0.5),
    ("C:C8", "C:C9", 1.0), ("C:C9", "C:C8", 0.3),
]


def f2():
    comps, pers = ents(F2_EDGES)
    save("f2_weaving_fig2", {
        "companies": companies(comps),
        "persons": persons({p: {} for p in pers}),
        "shareholdings": holdings(F2_EDGES),
        "family_links_known": links([("P:P2", "P:P3", "PARTNER_OF")]),
    }, {
        "controls": [["P:P1", "C:C4"], ["P:P2", "C:C5"], ["P:P2", "C:C6"], ["P:P2", "C:C7"], ["C:C8", "C:C9"]],
        "not_controls": [["P:P2", "C:C8"], ["P:P3", "C:C8"], ["P:P3", "C:C6"]],
        "families": [["P:P2", "P:P3"]],
        "family_controls": [{"members": ["P:P2", "P:P3"], "company": "C:C8"},    # 0.1 + 0.5
                            {"members": ["P:P2", "P:P3"], "company": "C:C9"}],
        "close_links_contains": [["C:C6", "C:C8"], ["C:C4", "C:C7"]],            # P3 .4/.5; Phi = .4*.2 + .12
        "phi": {"C:C4|C:C7": 0.2},
        # Unrolled drops walks that come back to their source, so C8->C9 is exact (1.0) under both
        # methods; a cycle among INTERMEDIATES still inflates it: P3->C8->C9->C8->C9 adds .5*1*.3*1
        "phi_paths": {"C:C8|C:C9": 1.0, "P:P3|C:C9": 0.5},
        "phi_unrolled_gt": {"P:P3|C:C9": 0.5},
    })


# ---------------------------------------------------------------- F3: P3 Figure 2 — the Acme Bank STR case
F3_EDGES = [
    ("C:PEOPLE_BANK", "C:ACME_TRUST", 0.93), ("C:ACME_TRUST", "C:MY_BANK", 0.23), ("P:P2", "C:MY_BANK", 0.34),
    ("C:MY_BANK", "C:C3", 0.55), ("C:C3", "C:C4", 1.0), ("C:C4", "C:C6", 0.51), ("C:C6", "C:C7", 0.6),
    ("C:C6", "C:C8", 0.6), ("C:C7", "C:ACME_BANK", 0.25), ("C:C8", "C:ACME_BANK", 0.21),
    ("C:MY_BANK", "C:ACME_BANK", 0.06),
    # distractors
    ("C:MY_BANK", "C:C1", 0.7), ("C:MY_BANK", "C:C2", 0.12), ("C:C3", "C:C5", 0.4),
    ("C:C6", "C:C9", 0.03), ("C:C8", "C:C10", 0.11),
]
F3_BANKS = ("C:MY_BANK", "C:PEOPLE_BANK", "C:ACME_BANK")


def f3():
    comps, _ = ents(F3_EDGES)
    comps = sorted(set(comps) | {"C:ACME_TRUST"})
    # X and P1 are partners: same address and province, opposite sex, similar age (for the Bayes test)
    pers = persons({
        "P:X": {"sex": "F", "birth_year": 1975, "address": "7 Via Roma", "province": "PR01", "has_record": 1,
                "surname": "Ferri"},
        "P:P1": {"sex": "M", "birth_year": 1972, "address": "7 Via Roma", "province": "PR01", "surname": "Conti"},
        "P:P2": {"sex": "F", "birth_year": 1970, "surname": "Conti", "birth_city": "Lucca"},
        "P:P3": {"sex": "M", "birth_year": 1968, "surname": "Conti", "birth_city": "Lucca"},
    })
    save("f3_acme", {
        "companies": companies(comps, banks=F3_BANKS),
        "persons": pers,
        "shareholdings": holdings(F3_EDGES),
        "roles": pd.DataFrame([{"person_eid": "P:P1", "company_eid": "C:PEOPLE_BANK", "role": "CEO"}]),
        "family_links_known": links([("P:X", "P:P1", "PARTNER_OF"), ("P:P1", "P:P2", "SIBLING_OF"),
                                     ("P:P2", "P:P3", "SIBLING_OF")]),
        "loans": pd.DataFrame([{"loan_id": "L1", "applicant_eid": "P:X", "lender_eid": "C:ACME_BANK",
                                "amount": 250000.0, "requested_on": "2026-03-01"}]),
        "strs": pd.DataFrame([{"str_id": "S1", "num": 1, "subject_eid": "P:X", "bank_eid": "C:ACME_BANK",
                               "instrument_type": "LOAN", "instrument_id": "L1", "amount": 250000.0,
                               "filed_on": "2026-03-05"}]),
    }, {
        "controls": [["P:P1", "C:PEOPLE_BANK"], ["P:P1", "C:ACME_TRUST"], ["C:MY_BANK", "C:ACME_BANK"],
                     ["C:MY_BANK", "C:C8"]],
        "not_controls": [["P:X", "C:ACME_BANK"], ["P:P1", "C:MY_BANK"], ["P:P2", "C:MY_BANK"]],
        "phi": {"P:P1|C:MY_BANK": 0.2139},                                   # 1.0 (CEO) * 0.93 * 0.23
        "families": [["P:P1", "P:P2", "P:P3", "P:X"]],
        "family_accumulated_share": {"C:MY_BANK": 0.5539},                   # P3: 0.34 + 0.21 = 0.55
        "family_controls": [{"members": ["P:P1", "P:P2", "P:P3", "P:X"], "company": "C:MY_BANK"},   # .34 + .23
                            {"members": ["P:P1", "P:P2", "P:P3", "P:X"], "company": "C:ACME_BANK"}],  # .06+.25+.21
        "findings": {"S1": ["P3.R10", "P3.PYRAMID", "P4.RECORD"]},           # X has a record (P3's red node)
        "score_min": {"S1": 0.8},                                            # 1 - .15 * .7 * .85 = 0.91075
        "explain_contains": {"S1": ["0.34", "0.23", "0.52", "PARTNER_OF"]},
    })


# ---------------------------------------------------------------- F4: P3 slush-fund rules (Eq. 1-2)
def f4():
    comps = ["C:A", "C:B", "C:D", "C:BANK"]
    save("f4_slush", {
        "companies": companies(comps, banks=("C:BANK",)),
        "persons": persons({"P:OWNER": {}}),
        "shareholdings": holdings([("P:OWNER", "C:A", 1.0)]),
        "accounts": pd.DataFrame([
            {"account_id": f"A:{c[2:]}", "holder_eid": c, "bank_eid": "C:BANK", "country": "IT",
             "opened_on": "2020-01-01"} for c in ["C:A", "C:B", "C:D"]]),
        "transfers": pd.DataFrame([
            {"transfer_id": "T1", "from_account": "A:A", "to_account": "A:B", "amount": 5000.0,
             "ts": "2026-02-01 10:00:00", "product": "consulting"},
            {"transfer_id": "T3", "from_account": "A:A", "to_account": "A:D", "amount": 7000.0,
             "ts": "2026-02-02 10:00:00", "product": "hardware"},
        ]),
        "invoices": pd.DataFrame([
            {"invoice_id": "I1", "issuer_eid": "C:B", "payee_eid": "C:A", "product": "consulting",
             "amount": 5000.0, "issued_on": "2026-02-01"},
            {"invoice_id": "I2", "issuer_eid": "C:B", "payee_eid": "C:A", "product": "software",
             "amount": 9000.0, "issued_on": "2026-02-03"},
        ]),
    }, {
        "potential_slush_fund": ["C:B"],          # I2 invoiced, never paid (P3 Rule 2)
        "missing_invoice": ["T3"],                # paid, never invoiced (inverse of P3 Rule 1)
        "clean_transfers": ["T1"],
    })


# ---------------------------------------------------------------- F5: P4 Level-2 analyst toy
def f5():
    save("f5_level2", {
        "companies": companies(["C:BANK1"], banks=("C:BANK1",)),
        "persons": persons({"P:PEP": {"is_pep": 1}, "P:OFF": {}}),
        "shareholdings": holdings([]),
        "accounts": pd.DataFrame([
            {"account_id": "A:PEP", "holder_eid": "P:PEP", "bank_eid": "C:BANK1", "country": "IT", "opened_on": "2019-01-01"},
            {"account_id": "A:OFF", "holder_eid": "P:OFF", "bank_eid": "C:BANK1", "country": "BS", "opened_on": "2019-01-01"},
            # holder C:XYZ is not in the company register -> unknown counterparty
            {"account_id": "A:XYZ", "holder_eid": "C:XYZ", "bank_eid": "C:BANK1", "country": "IT", "opened_on": "2025-12-01"},
        ]),
        "transfers": pd.DataFrame([
            {"transfer_id": "T1", "from_account": "A:OFF", "to_account": "A:PEP", "amount": 9500.0,
             "ts": "2026-04-01 11:00:00", "product": None},
            {"transfer_id": "T2", "from_account": "A:XYZ", "to_account": "A:PEP", "amount": 4000.0,
             "ts": "2026-04-03 15:00:00", "product": None},
        ]),
        "strs": pd.DataFrame([{"str_id": "S5", "num": 1, "subject_eid": "P:PEP", "bank_eid": "C:BANK1",
                               "instrument_type": "TRANSFER", "instrument_id": "T1", "amount": 9500.0,
                               "filed_on": "2026-04-05"}]),
    }, {
        "findings": {"S5": ["P4.NEAR_MISS", "P4.PEP_HIGH_RISK", "P4.UNKNOWN_CP"]},
        "score_min": {"S5": 0.6},                 # 1 - (1-.3)(1-.5)(1-.3) = 0.755
    })


if __name__ == "__main__":
    for build in (f1, f2, f3, f4, f5):
        build()
