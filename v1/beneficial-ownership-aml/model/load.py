"""Declarative loading of contract tables into the ontology (P1 Alg. 2 "input mapping").

A source is either local frames (fixtures, bundled CSVs) or Snowflake tables. Loading never
loops over rows: each table is one or a few `define` rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from model.contracts import CONTRACTS, EVAL_ONLY, read_dir

ROOT = Path(__file__).resolve().parents[1]


class DataSource:
    def has(self, name: str) -> bool: ...
    def rows(self, model, name: str): ...
    def frame(self, name: str) -> pd.DataFrame: ...


@dataclass
class FrameSource(DataSource):
    tables: dict[str, pd.DataFrame]
    shared: dict[str, pd.DataFrame] = field(default_factory=dict)

    @classmethod
    def from_dir(cls, path) -> "FrameSource":
        t = read_dir(path)
        shared = read_dir_shared()
        return cls({k: v for k, v in t.items() if k not in EVAL_ONLY}, shared)

    def _frame(self, name):
        df = self.tables.get(name)
        if df is None or df.empty:
            df = self.shared.get(name)
        return df

    def has(self, name):
        df = self._frame(name)
        return df is not None and not df.empty

    def frame(self, name):
        """A table as a DataFrame (task tables for the GNNs, calibration pairs)."""
        if name in EVAL_ONLY:
            raise ValueError(f"{name} is evaluation-only ground truth")
        return self._frame(name).reset_index(drop=True).copy()

    def rows(self, model, name):
        if name in EVAL_ONLY:
            raise ValueError(f"{name} is evaluation-only ground truth and must never be loaded into the model")
        df = self._frame(name).reset_index(drop=True).copy()
        for col, t in CONTRACTS[name].items():
            if t == "datetime":
                df[col] = pd.to_datetime(df[col])
            elif t == "date":
                df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d")
            elif t == "float":
                df[col] = df[col].astype(float)
            elif t == "int":
                df[col] = df[col].astype("int64")
        # On Snowflake, model.data drops every row holding a null or "" in ANY column, so optional
        # columns never travel in the main frame; read them with optional() instead.
        df = df.drop(columns=[c for c, t in CONTRACTS[name].items() if t == "str?"])
        return model.data(df)

    def optional(self, model, name, key, col):
        """(key, col) rows where the optional column has a value, or None if there are none."""
        df = self._frame(name)[[key, col]]
        df = df[df[col].notna() & (df[col].astype(str) != "")].reset_index(drop=True)
        return model.data(df) if len(df) else None


@dataclass
class TableSource(DataSource):
    db_schema: str
    present: set[str] | None = None

    def rows(self, model, name):
        if name in EVAL_ONLY:
            raise ValueError(f"{name} is evaluation-only ground truth and must never be loaded into the model")
        if not self._in_snowflake(name):
            return FrameSource({}, read_dir_shared()).rows(model, name)
        return model.Table(f"{self.db_schema}.{name.upper()}")

    def optional(self, model, name, key, col):
        return model.Table(f"{self.db_schema}.{name.upper()}")   # NULLs simply don't match

    def frame(self, name):
        if name in EVAL_ONLY:
            raise ValueError(f"{name} is evaluation-only ground truth")
        if not self._in_snowflake(name):
            return read_dir_shared()[name]
        from relationalai.semantics import Model

        df = Model("bo_aml_frames").config.get_session().table(f"{self.db_schema}.{name.upper()}").to_pandas()
        df.columns = [c.lower() for c in df.columns]
        return df

    def _in_snowflake(self, name):
        if self.present is None:
            from relationalai.semantics import Model

            db, schema = self.db_schema.split(".")
            rows = Model("bo_aml_catalog").config.get_session().sql(
                f"SELECT TABLE_NAME FROM {db}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{schema}'").collect()
            self.present = {r[0].lower() for r in rows}
        return name in self.present

    def has(self, name):
        return self._in_snowflake(name) or name in read_dir_shared()


@dataclass
class Only(DataSource):
    """Restrict a source to some tables (the GNN exports treat multi-valued relations such as
    Person.is_ceo_at as functional, so GNN models load only what they use)."""
    inner: DataSource
    tables: frozenset

    def has(self, name):
        return name in self.tables and self.inner.has(name)

    def rows(self, model, name):
        return self.inner.rows(model, name)

    def optional(self, model, name, key, col):
        return self.inner.optional(model, name, key, col)

    def frame(self, name):
        return self.inner.frame(name)


def read_dir_shared() -> dict[str, pd.DataFrame]:
    """rule_catalog and high_risk_jurisdictions ship once in data/ and apply to every source."""
    out = {}
    for name in ("rule_catalog", "high_risk_jurisdictions", "analysts"):
        f = ROOT / "data" / f"{name}.csv"
        if f.exists():
            out[name] = pd.read_csv(f)
    return out


def load(model, o, source: DataSource) -> None:
    m = model
    E, Co, Pe = o.Entity, o.Company, o.Person
    if not source.has("companies") or not source.has("persons"):
        raise ValueError("companies and persons are required")

    src = source.rows(m, "companies")
    m.define(Co.new(src.to_schema(exclude=["is_bank"])))
    m.where(c := Co.lookup(eid=src.eid), src.is_bank == 1).define(c.is_bank())

    src = source.rows(m, "persons")
    m.define(Pe.new(src.to_schema(exclude=["is_pep", "has_record"])))
    m.where(p := Pe.lookup(eid=src.eid), src.is_pep == 1).define(p.is_pep())
    m.where(p := Pe.lookup(eid=src.eid), src.has_record == 1).define(p.has_record())

    if source.has("shareholdings"):
        sh = source.rows(m, "shareholdings")
        m.where(ow := E.lookup(eid=sh.owner_eid), c := Co.lookup(eid=sh.owned_eid),
                sh.right_type == "ownership").define(ow.owns(c, sh.share))

    if source.has("roles"):
        r = source.rows(m, "roles")
        m.where(p := Pe.lookup(eid=r.person_eid), c := Co.lookup(eid=r.company_eid), r.role == "CEO").define(p.is_ceo_at(c))

    if source.has("family_links_known"):
        fl = source.rows(m, "family_links_known")
        m.where(a := Pe.lookup(eid=fl.a_eid), b := Pe.lookup(eid=fl.b_eid)).define(a.link(b, fl.link_type, 1.0))

    if source.has("accounts"):
        a = source.rows(m, "accounts")
        m.define(o.Account.new(a.to_schema(exclude=["bank_eid"])))
        m.where(acc := o.Account.lookup(account_id=a.account_id), h := E.lookup(eid=a.holder_eid)).define(acc.holder(h))
        m.where(acc := o.Account.lookup(account_id=a.account_id), b := Co.lookup(eid=a.bank_eid)).define(acc.bank(b))

    if source.has("transfers"):
        t = source.rows(m, "transfers")
        m.define(o.Transfer.new(t.to_schema(exclude=["from_account", "to_account", "product"])))
        m.where(tr := o.Transfer.lookup(transfer_id=t.transfer_id), f := o.Account.lookup(account_id=t.from_account),
                to := o.Account.lookup(account_id=t.to_account)).define(tr.from_account(f), tr.to_account(to))
        tp = source.optional(m, "transfers", "transfer_id", "product")
        if tp is not None:
            m.where(tr := o.Transfer.lookup(transfer_id=tp.transfer_id), tp.product != "").define(tr.product(tp.product))

    if source.has("invoices"):
        i = source.rows(m, "invoices")
        m.define(o.Invoice.new(i.to_schema(exclude=["issuer_eid", "payee_eid"])))
        m.where(inv := o.Invoice.lookup(invoice_id=i.invoice_id), a := E.lookup(eid=i.issuer_eid),
                b := E.lookup(eid=i.payee_eid)).define(inv.issuer(a), inv.payee(b))

    if source.has("loans"):
        ln = source.rows(m, "loans")
        m.define(o.Loan.new(ln.to_schema(exclude=["applicant_eid", "lender_eid"])))
        m.where(lo := o.Loan.lookup(loan_id=ln.loan_id), a := Pe.lookup(eid=ln.applicant_eid),
                b := Co.lookup(eid=ln.lender_eid)).define(lo.applicant(a), lo.lender(b))

    if source.has("strs"):
        s = source.rows(m, "strs")
        m.define(o.STR.new(s.to_schema(exclude=["subject_eid", "bank_eid"])))
        m.where(st := o.STR.lookup(str_id=s.str_id), x := E.lookup(eid=s.subject_eid)).define(st.subject(x))
        m.where(st := o.STR.lookup(str_id=s.str_id), b := Co.lookup(eid=s.bank_eid)).define(st.bank(b))
        st = o.STR.ref()
        m.where(st.instrument_type == "LOAN", lo := o.Loan.lookup(loan_id=st.instrument_id)).define(st.loan(lo))
        m.where(st.instrument_type == "TRANSFER", tr := o.Transfer.lookup(transfer_id=st.instrument_id)).define(st.transfer(tr))

    if source.has("high_risk_jurisdictions"):
        m.define(o.HighRisk.new(source.rows(m, "high_risk_jurisdictions").to_schema()))
    if source.has("rule_catalog"):
        m.define(o.Rule.new(source.rows(m, "rule_catalog").to_schema()))
    if source.has("analysts"):
        m.define(o.Analyst.new(source.rows(m, "analysts").to_schema()))


def load_links(model, o, links: pd.DataFrame) -> None:
    """Links predicted in earlier VADA-LINK rounds (columns a_eid, b_eid, link_type, confidence)."""
    if links is None or links.empty:
        return
    df = links[["a_eid", "b_eid", "link_type", "confidence"]].reset_index(drop=True).astype({"confidence": float})
    d = model.data(df)
    model.where(a := o.Person.lookup(eid=d.a_eid), b := o.Person.lookup(eid=d.b_eid)).define(
        a.link(b, d.link_type, d.confidence))
