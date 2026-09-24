"""Table contracts shared by the fixtures, the generator, the loaders and Snowflake.

Every id is a string with a type prefix: C: company, P: person, F: family (derived), A: account.
"""

import pandas as pd

CONTRACTS: dict[str, dict[str, str]] = {
    "companies": {"eid": "str", "name": "str", "legal_form": "str", "sector": "str", "province": "str",
                  "inc_date": "date", "is_bank": "int"},
    "persons": {"eid": "str", "num": "int", "first_name": "str", "surname": "str", "sex": "str",
                "birth_date": "date", "birth_year": "int", "birth_city": "str", "address": "str",
                "province": "str", "is_pep": "int", "has_record": "int"},
    "shareholdings": {"owner_eid": "str", "owned_eid": "str", "share": "float", "right_type": "str"},
    "roles": {"person_eid": "str", "company_eid": "str", "role": "str"},
    "family_links_known": {"a_eid": "str", "b_eid": "str", "link_type": "str", "source": "str"},
    "family_links_hidden": {"a_eid": "str", "b_eid": "str", "link_type": "str"},
    "family_pairs_train": {"a_eid": "str", "b_eid": "str", "link_type": "str", "label": "int"},
    "family_pairs_val": {"a_eid": "str", "b_eid": "str", "link_type": "str", "label": "int"},
    "family_pairs_test": {"a_eid": "str", "b_eid": "str", "link_type": "str", "label": "int"},
    "accounts": {"account_id": "str", "holder_eid": "str", "bank_eid": "str", "country": "str", "opened_on": "date"},
    "transfers": {"transfer_id": "str", "from_account": "str", "to_account": "str", "amount": "float",
                  "ts": "datetime", "product": "str?"},
    "invoices": {"invoice_id": "str", "issuer_eid": "str", "payee_eid": "str", "product": "str",
                 "amount": "float", "issued_on": "date"},
    "loans": {"loan_id": "str", "applicant_eid": "str", "lender_eid": "str", "amount": "float", "requested_on": "date"},
    "strs": {"str_id": "str", "num": "int", "subject_eid": "str", "bank_eid": "str", "instrument_type": "str",
             "instrument_id": "str", "amount": "float", "filed_on": "date"},
    "str_labels": {"str_id": "str", "is_laundering": "int", "offence": "str"},
    "account_labels_train": {"account_id": "str", "ts": "datetime", "label": "int"},
    "account_labels_val": {"account_id": "str", "ts": "datetime", "label": "int"},
    "account_labels_test": {"account_id": "str", "ts": "datetime", "label": "int"},
    "high_risk_jurisdictions": {"country": "str"},
    "rule_catalog": {"rule_id": "str", "weight": "float", "offence": "str", "priority": "int", "description": "str"},
    "analysts": {"analyst_id": "str", "hours": "float", "skills": "str"},
}

# Tables the model must never see: ground truth for evaluation only.
EVAL_ONLY = {"family_links_hidden", "str_labels", "account_labels_test"}

# Tables every source must provide (the rest are optional).
REQUIRED = {"companies", "persons", "shareholdings"}

_DTYPE_CHECK = {
    "str": lambda s: s.map(lambda v: isinstance(v, str)).all(),
    "str?": lambda s: s.map(lambda v: v is None or isinstance(v, str) or pd.isna(v)).all(),
    "int": pd.api.types.is_integer_dtype,
    "float": pd.api.types.is_numeric_dtype,
    "date": lambda s: pd.api.types.is_datetime64_any_dtype(pd.to_datetime(s, errors="coerce"))
    and pd.to_datetime(s, errors="coerce").notna().all(),
    "datetime": lambda s: pd.to_datetime(s, errors="coerce").notna().all(),
}


class ContractError(ValueError):
    pass


def validate(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Check columns and types; return the frame with columns in contract order."""
    if name not in CONTRACTS:
        raise ContractError(f"unknown table {name!r}")
    spec = CONTRACTS[name]
    missing = [c for c in spec if c not in df.columns]
    extra = [c for c in df.columns if c not in spec]
    if missing or extra:
        raise ContractError(f"{name}: missing columns {missing}, unexpected columns {extra}")
    bad = [c for c, t in spec.items() if len(df) and not _DTYPE_CHECK[t](df[c])]
    if bad:
        raise ContractError(f"{name}: columns with wrong type {[(c, spec[c], str(df[c].dtype)) for c in bad]}")
    if name == "shareholdings" and len(df):
        dup = df.duplicated(["owner_eid", "owned_eid", "right_type"])
        if dup.any():
            raise ContractError(f"shareholdings: {int(dup.sum())} duplicate (owner, owned, right_type) rows")
        if ((df["share"] <= 0) | (df["share"] > 1)).any():
            raise ContractError("shareholdings: share must be in (0, 1]")
    return df[list(spec)]


def read_dir(path) -> dict[str, pd.DataFrame]:
    """Read every contract CSV present in a directory (fixtures, sample or CI data)."""
    from pathlib import Path

    out = {}
    for name, spec in CONTRACTS.items():
        f = Path(path) / f"{name}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, keep_default_na=False, na_values={c: [""] for c, t in spec.items() if t != "str"})
        for c, t in spec.items():
            if t == "str?" and c in df:
                df[c] = df[c].replace({"": None})
        out[name] = validate(df, name)
    missing = REQUIRED - out.keys()
    if missing:
        raise ContractError(f"{path}: missing required tables {sorted(missing)}")
    return out


def write_dir(tables: dict[str, pd.DataFrame], path) -> None:
    from pathlib import Path

    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        validate(df, name).to_csv(p / f"{name}.csv", index=False)
