"""Seeded synthetic data for the template: ownership graph, persons and families, transactions,
planted laundering structures, STRs and train/val/test splits. Follows PLAN.md §2.3.

    python -m data.generator.generate --seed 7 --companies 5000 --persons 3000 --out data/sample
    python -m data.generator.generate --seed 7 --companies 500 --persons 300 --out data/ci

Everything is synthetic: names are built from syllables, places are invented, and no record
describes a real person or company.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from model.contracts import write_dir

DENSITY = {"sparse": 0.5, "normal": 1.0, "dense": 2.0, "superdense": 4.0}
HIGH_RISK = ["BS", "KY", "PA", "VG"]
FOREIGN = ["FR", "DE", "CH", "GB", "US", "ES", "AT"]
START = datetime(2026, 1, 1)
SYL = ["ba", "ce", "di", "fo", "gu", "la", "me", "ni", "po", "ru", "sa", "te", "vi", "zo", "ca", "lo",
       "mar", "ren", "tin", "gal", "ber", "cor", "dan", "fer", "gio", "len", "mon", "pas", "ros", "val"]


@dataclass
class GenConfig:
    seed: int = 7
    companies: int = 5000
    persons: int = 3000
    days: int = 180
    density: str = "normal"
    holdout: float = 0.2
    ubo_hidden_frac: float = 0.4      # share of UBO-loan partner links forced into the hidden set
    transfers_per_account_day: float = 0.012

    @property
    def scale(self) -> float:
        return self.companies / 5000


class Gen:
    def __init__(self, cfg: GenConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.manifest: dict[str, list] = defaultdict(list)
        self.planted_edges: set[tuple[str, str]] = set()

    def pick(self, seq):
        """One element of a large list (rng.choice converts the whole list to an array on every call)."""
        return seq[int(self.rng.integers(len(seq)))]

    # ------------------------------------------------------------------ vocabulary
    def word(self, n_syl):
        return "".join(self.rng.choice(SYL, n_syl)).capitalize()

    def pools(self):
        r = self.rng
        self.surnames = list(dict.fromkeys(self.word(r.integers(2, 4)) + r.choice(["i", "o", "a", "ini", "etti"])
                                           for _ in range(2600)))[:2000]
        w = 1.0 / np.arange(1, len(self.surnames) + 1) ** 1.1
        self.surname_p = w / w.sum()
        self.surname_cdf = np.cumsum(self.surname_p)
        self.first_m = [self.word(2) + "o" for _ in range(150)]
        self.first_f = [self.word(2) + "a" for _ in range(150)]
        self.provinces = [f"PR{i:02d}" for i in range(60)]
        self.cities = [(self.word(2) + r.choice(["ano", "ello", "ino", "ona"]), self.provinces[i % 60]) for i in range(300)]
        self.streets = [self.word(2) + r.choice(["", " Nuova", " Vecchia"]) for _ in range(500)]
        self.sectors = ["MANUFACTURING", "RETAIL", "CONSTRUCTION", "REAL_ESTATE", "LOGISTICS", "CONSULTING",
                        "HOSPITALITY", "AGRICULTURE", "SOFTWARE", "HOLDING"]
        self.products = ["consulting", "software", "hardware", "logistics", "construction", "marketing", "catering"]

    def address(self, city):
        return f"{self.rng.integers(1, 200)} Via {self.rng.choice(self.streets)}, {city}"

    def typo(self, s):
        i = self.rng.integers(len(s))
        return s[:i] + self.rng.choice(list("aeiorstn")) + s[i + 1:]

    # ------------------------------------------------------------------ 1. persons and families
    def gen_persons(self):
        r, n = self.rng, self.cfg.persons
        rows, true_links, fam_of = [], [], {}
        fam = 0
        while len(rows) < n:
            size = int(r.choice([1, 2, 3, 4, 5], p=[0.40, 0.30, 0.15, 0.10, 0.05]))
            size = min(size, n - len(rows))
            ci = r.integers(len(self.cities))
            city, prov = self.cities[ci]
            home = self.address(city)
            father_surname = self.surnames[min(int(np.searchsorted(self.surname_cdf, r.random())), len(self.surnames) - 1)]
            base_year = int(r.integers(1940, 1985))
            members = []
            for k in range(size):
                if k == 0:
                    sex, sur, by, addr, bcity = "M", father_surname, base_year, home, city
                elif k == 1:  # spouse
                    sex = "F" if r.random() < 0.95 else "M"
                    sur = father_surname if r.random() < 0.2 else self.surnames[min(int(np.searchsorted(self.surname_cdf, r.random())), len(self.surnames) - 1)]
                    by = base_year + int(r.integers(-8, 9))
                    addr = home if r.random() < 0.85 else self.address(self.cities[r.integers(len(self.cities))][0])
                    bcity = self.cities[r.integers(len(self.cities))][0]
                else:  # children
                    sex = "M" if r.random() < 0.5 else "F"
                    sur, by = father_surname, base_year + int(r.integers(24, 36))
                    addr = home if r.random() < 0.5 else self.address(city)
                    bcity = city if r.random() < 0.6 else self.cities[r.integers(len(self.cities))][0]
                if r.random() < 0.05:
                    sur = self.typo(sur)
                if r.random() < 0.10:
                    addr = self.address(self.cities[r.integers(len(self.cities))][0])
                num = len(rows) + 1
                eid = f"P:{num}"
                first = r.choice(self.first_m if sex == "M" else self.first_f)
                rows.append({"eid": eid, "num": num, "first_name": first, "surname": sur, "sex": sex,
                             "birth_date": f"{by}-{r.integers(1, 13):02d}-{r.integers(1, 29):02d}", "birth_year": by,
                             "birth_city": bcity, "address": addr, "province": prov,
                             "is_pep": int(r.random() < 0.005), "has_record": int(r.random() < 0.02)})
                members.append(eid)
                fam_of[eid] = fam
            if size >= 2:
                true_links.append((members[0], members[1], "PARTNER_OF"))
            kids = members[2:]
            for i in range(len(kids)):
                for p in members[:2]:
                    true_links.append((p, kids[i], "PARENT_OF"))
                for j in range(i + 1, len(kids)):
                    true_links.append((kids[i], kids[j], "SIBLING_OF"))
            self.manifest["families"].append(members)
            fam += 1
        self.persons = pd.DataFrame(rows)
        self.person_ids = list(self.persons["eid"])
        self.true_links = true_links
        self.fam_of = fam_of
        self.family_members = self.manifest["families"]

    # ------------------------------------------------------------------ 2. companies
    def gen_companies(self):
        r, n = self.rng, self.cfg.companies
        n_banks = max(20, int(0.02 * n))
        bank_idx = set(r.choice(np.arange(5, n), n_banks, replace=False).tolist())
        rows = []
        for i in range(n):
            city, prov = self.cities[r.integers(len(self.cities))]
            is_bank = i in bank_idx
            rows.append({"eid": f"C:{i}", "name": f"{self.word(2)} {'Banca' if is_bank else r.choice(['SpA', 'Srl', 'Group'])}",
                         "legal_form": "SPA" if is_bank else str(r.choice(["SPA", "SRL", "SNC"], p=[0.3, 0.6, 0.1])),
                         "sector": "BANKING" if is_bank else str(r.choice(self.sectors)), "province": prov,
                         "inc_date": (date(1980, 1, 1) + timedelta(days=int(i / n * 16000))).isoformat(),
                         "is_bank": int(is_bank)})
        self.companies = pd.DataFrame(rows)
        self.banks = [f"C:{i}" for i in sorted(bank_idx)]

    # ------------------------------------------------------------------ 3. ownership (Barabási–Albert variant)
    def gen_ownership(self):
        r, cfg = self.rng, self.cfg
        lam = (cfg.persons / cfg.companies) * DENSITY[cfg.density]
        person_urn = list(self.persons["eid"])
        company_urn: list[str] = []
        holds: dict[tuple[str, str], float] = {}
        for i in range(cfg.companies):
            cid = f"C:{i}"
            k = 1 + int(r.poisson(lam))
            owners = set()
            for _ in range(k):
                if company_urn and r.random() >= 0.7:
                    o = company_urn[r.integers(len(company_urn))]
                else:
                    o = person_urn[r.integers(len(person_urn))]
                owners.add(o)
            owners = sorted(owners)
            shares = r.beta(8, 1) * r.dirichlet(0.8 * np.ones(len(owners)))
            for o, s in zip(owners, shares):
                if s >= 0.001:
                    holds[(o, cid)] = round(float(s), 4)
                    (company_urn if o.startswith("C:") else person_urn).append(o)
            company_urn.append(cid)
            if r.random() < 0.0007:
                holds[(cid, cid)] = round(float(r.uniform(0.01, 0.1)), 4)
                self.manifest["buybacks"].append(cid)
        self.holds = holds

    def plant(self, owner, owned, share, tag=None):
        self.holds[(owner, owned)] = round(float(share), 4)
        self.planted_edges.add((owner, owned))

    def pick_companies(self, n, exclude=(), banks_ok=False):
        """n distinct companies not in `exclude` (rejection sampling: O(n) per call, not O(#companies))."""
        if not hasattr(self, "_bank_set"):
            self._bank_set = set(self.banks)
        exclude = exclude if isinstance(exclude, set) else set(exclude)
        out, seen = [], set()
        N = self.cfg.companies
        while len(out) < n:
            c = f"C:{int(self.rng.integers(N))}"
            if c in exclude or c in seen or (not banks_ok and c in self._bank_set):
                continue
            seen.add(c)
            out.append(c)
        return out

    # ------------------------------------------------------------------ 4. planted ownership structures
    def plant_structures(self):
        r, s = self.rng, self.cfg.scale
        used: set[str] = set()
        self.used = used              # later plants (slush funds, minority bank stakes) must avoid these
        multi = [f for f in self.family_members if len(f) >= 2]

        def pyramid(top_owners, end_bank):
            L = int(r.integers(3, 9))
            chain = self.pick_companies(L, exclude=used)
            used.update(chain)
            if end_bank:
                bank = self.pick([b for b in self.banks if b not in used])
                used.add(bank)
                chain = chain + [bank]
            for owner, sh in top_owners:
                self.plant(owner, chain[0], sh)
            for a, b in zip(chain, chain[1:]):
                self.plant(a, b, r.uniform(0.51, 0.70))
            return chain

        for _ in range(max(2, int(40 * s))):
            chain = pyramid([(self.pick(self.person_ids), r.uniform(0.55, 0.8))], r.random() < 0.5)
            self.manifest["pyramids"].append(chain)
        for _ in range(max(2, int(30 * s))):
            grp = self.pick_companies(int(r.choice([2, 3])), exclude=used)
            for a in grp:
                for b in grp:
                    if a != b:
                        self.plant(a, b, r.uniform(0.05, 0.3))
            self.manifest["cross_holdings"].append(grp)
        for _ in range(max(2, int(60 * s))):
            fam = [m for m in multi[r.integers(len(multi))]][:4]
            c = self.pick_companies(1, exclude=used)[0]
            used.add(c)
            while True:
                sh = r.uniform(0.15, 0.45, len(fam))
                if sh.sum() > 0.5 and (sh < 0.5).all() and sh.sum() <= 1:
                    break
                if len(fam) == 2:
                    sh = np.array([r.uniform(0.26, 0.45), r.uniform(0.26, 0.45)])
                    break
            for m, x in zip(fam, sh):
                self.plant(m, c, x)
            self.manifest["family_businesses"].append({"company": c, "members": fam})
        for _ in range(max(2, int(40 * s))):
            p = self.pick(self.person_ids)
            a, b = self.pick_companies(2, exclude=used)
            self.plant(p, a, r.uniform(0.2, 0.4))
            self.plant(p, b, r.uniform(0.2, 0.4))
            self.manifest["close_link_pairs"].append([a, b, p])
        # UBO self-loan structures: a family jointly controls a pyramid ending in a bank;
        # another member (with no direct shares) will later borrow from that bank.
        self.ubo_cases = []
        for _ in range(max(3, int(25 * s))):
            fam = multi[r.integers(len(multi))]
            owners = fam[:2] if len(fam) >= 2 else fam
            applicant = fam[1] if len(fam) >= 2 else fam[0]
            holders = [m for m in fam if m != applicant] or owners
            sh = [r.uniform(0.28, 0.45) for _ in holders[:2]] if len(holders) >= 2 else [r.uniform(0.55, 0.8)]
            if len(holders) >= 2 and sum(sh) <= 0.5:
                sh[0] = 0.51 - sh[1] + 0.05
            chain = pyramid(list(zip(holders[:2], sh)), end_bank=True)
            self.ubo_cases.append({"applicant": applicant, "holders": holders[:2], "bank": chain[-1], "chain": chain})
        self.manifest["ubo_cases"] = self.ubo_cases
        # CEO roles
        roles = []
        roles_n = int(0.3 * self.cfg.companies)
        pool = [c for c in self.companies["eid"] if c not in used]
        for c in self.rng.choice(pool, min(roles_n, len(pool)), replace=False):
            roles.append({"person_eid": self.pick(self.person_ids), "company_eid": c, "role": "CEO"})
        self.roles = pd.DataFrame(roles, columns=["person_eid", "company_eid", "role"])

    def normalize_shares(self):
        """Keep planted edges; scale other incoming shares so each company's total is <= 1."""
        incoming = defaultdict(list)
        for (o, c), w in self.holds.items():
            incoming[c].append((o, w))
        for c, lst in incoming.items():
            total = sum(w for _, w in lst)
            if total <= 1.0:
                continue
            planted = sum(w for o, w in lst if (o, c) in self.planted_edges)
            others = total - planted
            if planted > 1.0:  # two planted structures collided: scale everything
                f = 0.999 / total
                for o, w in lst:
                    self.holds[(o, c)] = round(w * f, 4)
                continue
            f = max(0.0, (0.999 - planted) / others) if others else 0.0
            for o, w in lst:
                if (o, c) not in self.planted_edges:
                    nw = round(w * f, 4)
                    if nw < 0.001:
                        del self.holds[(o, c)]
                    else:
                        self.holds[(o, c)] = nw

    # ------------------------------------------------------------------ 5. accounts and background transfers
    def gen_accounts(self):
        r = self.rng
        rows = []
        self.acct_of = defaultdict(list)
        self.acct_bank = {}

        def add(holder, country=None):
            aid = f"A:{len(rows) + 1}"
            ctry = country or ("IT" if r.random() < 0.95 else str(r.choice(FOREIGN + HIGH_RISK, p=None)))
            rows.append({"account_id": aid, "holder_eid": holder, "bank_eid": self.pick(self.banks),
                         "country": ctry, "opened_on": (date(2015, 1, 1) + timedelta(days=int(r.integers(0, 3600)))).isoformat()})
            self.acct_of[holder].append(aid)
            self.acct_bank[aid] = rows[-1]["bank_eid"]
            return aid

        for p in self.persons["eid"]:
            for _ in range(int(r.integers(1, 3))):
                add(p)
        for c in self.companies["eid"]:
            for _ in range(int(r.integers(1, 4))):
                add(c)
        for i in range(max(3, int(0.005 * len(rows)))):   # holders missing from the register
            add(f"C:UNREG{i}")
        self._add_account = add
        self.accounts_rows = rows

    def ts(self, day=None):
        d = self.rng.integers(0, self.cfg.days) if day is None else day
        return START + timedelta(days=int(d), seconds=int(self.rng.integers(8 * 3600, 20 * 3600)))

    def gen_transfers(self):
        """Background payments, vectorized (a per-row Python loop is ~300x slower at 100K companies)."""
        r = self.rng
        accts = np.array([a["account_id"] for a in self.accounts_rows])
        holders = np.array([a["holder_eid"] for a in self.accounts_rows])
        self.holder = dict(zip(accts, holders))
        n = int(len(accts) * self.cfg.days * self.cfg.transfers_per_account_day)
        src, dst = r.integers(len(accts), size=n), r.integers(len(accts), size=n)
        keep = src != dst
        src, dst = src[keep], dst[keep]
        n = len(src)
        amounts = np.round(np.exp(r.normal(7, 1.2, n)), 2)
        days = r.integers(0, self.cfg.days, n)
        secs = r.integers(8 * 3600, 20 * 3600, n)
        ts = pd.Timestamp(START) + pd.to_timedelta(days, unit="D") + pd.to_timedelta(secs, unit="s")
        b2b = np.char.startswith(holders[src], "C:") & np.char.startswith(holders[dst], "C:") & (r.random(n) < 0.6)
        prods = np.array(self.products)[r.integers(len(self.products), size=n)]
        product = np.where(b2b, prods, None)
        self.bg_transfers = pd.DataFrame({
            "transfer_id": [f"T:{i + 1}" for i in range(n)], "from_account": accts[src], "to_account": accts[dst],
            "amount": amounts, "ts": ts.strftime("%Y-%m-%d %H:%M:%S"), "product": product})
        inv = b2b & (r.random(n) < 0.9)
        self.bg_invoices = pd.DataFrame({
            "invoice_id": [f"I:{i + 1}" for i in range(int(inv.sum()))], "issuer_eid": holders[dst][inv],
            "payee_eid": holders[src][inv], "product": prods[inv], "amount": amounts[inv],
            "issued_on": ts[inv].strftime("%Y-%m-%d")})
        self.transfers, self.invoices = [], []

    def add_transfer(self, a, b, amt, t, prod=None):
        tid = f"T:{len(self.bg_transfers) + len(self.transfers) + 1}"
        self.transfers.append({"transfer_id": tid, "from_account": a, "to_account": b, "amount": round(amt, 2),
                               "ts": t.strftime("%Y-%m-%d %H:%M:%S"), "product": prod})
        return tid

    def add_invoice(self, issuer, payee, prod, amt, d):
        self.invoices.append({"invoice_id": f"I:{len(self.bg_invoices) + len(self.invoices) + 1}", "issuer_eid": issuer, "payee_eid": payee,
                              "product": prod, "amount": round(amt, 2), "issued_on": d.isoformat()})

    # ------------------------------------------------------------------ 6-7. typologies, loans and STRs
    def gen_cases(self):
        r, s = self.rng, self.cfg.scale
        accts = [a["account_id"] for a in self.accounts_rows]
        rand_acct = lambda: accts[r.integers(len(accts))]  # noqa: E731
        persons = list(self.persons["eid"])
        self.loans, strs, labels = [], [], []
        self.pep_marks = set()

        def file(subject, bank, itype, iid, amount, when, positive, offence):
            n = len(strs) + 1
            strs.append({"str_id": f"S:{n}", "num": n, "subject_eid": subject, "bank_eid": bank,
                         "instrument_type": itype, "instrument_id": iid, "amount": round(float(amount), 2),
                         "filed_on": (when + timedelta(days=int(r.integers(2, 11)))).date().isoformat()})
            labels.append({"str_id": f"S:{n}", "is_laundering": int(positive), "offence": offence})

        def bank_of(acct):
            return self.acct_bank[acct]

        # --- transaction typologies on bad actors (P4)
        typologies = ["structuring", "near_miss", "fan_in", "fan_out", "cycle", "pep_high_risk"]
        offence = {"structuring": "STRUCTURING", "near_miss": "STRUCTURING", "fan_in": "LAYERING",
                   "fan_out": "LAYERING", "cycle": "LAYERING", "pep_high_risk": "CORRUPTION"}
        bad = r.choice(persons, max(6, int(75 * s)), replace=False)
        for p in bad:
            acct = self.acct_of[p][0]
            kinds = list(r.choice(typologies, int(r.integers(1, 3)), replace=False))
            report = None
            for kind in kinds:
                day = int(r.integers(10, self.cfg.days - 15))
                if kind == "structuring":
                    for d in range(day, day + 3):
                        for _ in range(int(r.integers(5, 9))):
                            tid = self.add_transfer(acct, rand_acct(), r.uniform(1800, 2400), self.ts(d))
                    report = report or ("TRANSFER", tid, 2000.0, self.ts(day + 2))
                elif kind == "near_miss":
                    tid = self.add_transfer(rand_acct(), acct, r.uniform(9000, 9999), self.ts(day))
                    report = ("TRANSFER", tid, 9500.0, self.ts(day))
                elif kind in ("fan_in", "fan_out"):
                    for _ in range(int(r.integers(10, 21))):
                        other, t = rand_acct(), self.ts(day + int(r.integers(0, 3)))
                        tid = self.add_transfer(other, acct, r.uniform(500, 3000), t) if kind == "fan_in" \
                            else self.add_transfer(acct, other, r.uniform(500, 3000), t)
                    report = report or ("TRANSFER", tid, 2000.0, self.ts(day + 3))
                elif kind == "cycle":
                    ring = [acct] + [rand_acct() for _ in range(int(r.integers(2, 6)))]
                    amt = r.uniform(20000, 80000)
                    for k, (a, b) in enumerate(zip(ring, ring[1:] + [acct])):
                        tid = self.add_transfer(a, b, amt, self.ts(day + 2 * k))
                        amt *= 1 - r.uniform(0.02, 0.05)
                    report = report or ("TRANSFER", tid, amt, self.ts(day + 10))
                elif kind == "pep_high_risk":
                    self.pep_marks.add(p)
                    foreign = self._add_account(f"C:UNREG_OFF{len(self.manifest['pep_cases'])}", str(r.choice(HIGH_RISK)))
                    tid = self.add_transfer(foreign, acct, r.uniform(15000, 60000), self.ts(day))
                    self.manifest["pep_cases"].append(p)
                    report = ("TRANSFER", tid, 30000.0, self.ts(day))
            itype, iid, amount, when = report
            file(p, bank_of(acct), itype, iid, amount, when, True, offence[kinds[0]])
            self.manifest["bad_actors"].append({"person": p, "typologies": kinds})

        # --- slush funds: invoices with no payment (P3 Eq. 2), owned >50% by a person
        comp_list = list(self.companies["eid"])
        for _ in range(max(3, int(15 * s))):
            c = self.pick_companies(1, exclude=self.used)[0]   # never a planted structure's company
            self.used.add(c)
            owner = self.pick(persons)
            self.plant(owner, c, 0.8)
            for _ in range(int(r.integers(2, 5))):
                payee = comp_list[r.integers(len(comp_list))]
                self.add_invoice(c, payee, str(r.choice(self.products)), r.uniform(5000, 40000),
                                 (START + timedelta(days=int(r.integers(0, self.cfg.days)))).date())
            acct = self.acct_of[owner][0]
            tid = self.add_transfer(self.acct_of[c][0], acct, r.uniform(10000, 30000), self.ts())
            file(owner, bank_of(acct), "TRANSFER", tid, 20000, self.ts(), True, "FALSE_INVOICING")
            self.manifest["slush_funds"].append({"company": c, "owner": owner})

        # --- UBO self-loans (P3 Rule 10)
        for case in self.ubo_cases:
            lid = f"L:{len(self.loans) + 1}"
            when = self.ts()
            amt = float(r.uniform(1e5, 1e6))
            self.loans.append({"loan_id": lid, "applicant_eid": case["applicant"], "lender_eid": case["bank"],
                               "amount": round(amt, 2), "requested_on": when.date().isoformat()})
            file(case["applicant"], case["bank"], "LOAN", lid, amt, when, True, "SELF_LENDING")

        n_pos = len(strs)
        # --- benign STRs, 30% hard negatives
        for i in range(3 * n_pos):
            kind = r.choice(["benign", "hard_bank_minority", "hard_round", "hard_pep_domestic"], p=[0.7, 0.1, 0.1, 0.1])
            p = self.pick(persons)
            acct = self.acct_of[p][0]
            when = self.ts()
            if kind == "hard_bank_minority":
                bank = self.pick([b for b in self.banks if b not in self.used] or self.banks)
                self.plant(p, bank, r.uniform(0.1, 0.4))
                lid = f"L:{len(self.loans) + 1}"
                amt = float(r.uniform(1e5, 1e6))
                self.loans.append({"loan_id": lid, "applicant_eid": p, "lender_eid": bank,
                                   "amount": round(amt, 2), "requested_on": when.date().isoformat()})
                file(p, bank, "LOAN", lid, amt, when, False, "NONE")
                continue
            if kind == "hard_round":
                amt = float(r.choice([20000, 25000, 50000]))
            elif kind == "hard_pep_domestic":
                self.pep_marks.add(p)
                amt = float(r.uniform(12000, 30000))
            else:
                amt = float(r.uniform(10000, 40000))
            tid = self.add_transfer(rand_acct(), acct, amt, when)
            file(p, bank_of(acct), "TRANSFER", tid, amt, when, False, "NONE")
        self.strs, self.str_labels = pd.DataFrame(strs), pd.DataFrame(labels)
        self.persons.loc[self.persons["eid"].isin(self.pep_marks), "is_pep"] = 1

    # ------------------------------------------------------------------ 8. splits
    def gen_splits(self):
        r, cfg = self.rng, self.cfg
        predicted = [lk for lk in self.true_links if lk[2] in ("PARTNER_OF", "SIBLING_OF")]
        forced = {tuple(sorted((c["applicant"], h))) for c in self.ubo_cases for h in c["holders"]}
        hidden = []
        known = [lk for lk in self.true_links if lk[2] == "PARENT_OF"]
        for lk in predicted:
            key = tuple(sorted(lk[:2]))
            force = key in forced and r.random() < cfg.ubo_hidden_frac
            (hidden if force or r.random() < cfg.holdout else known).append(lk)
        self.known = pd.DataFrame([{"a_eid": a, "b_eid": b, "link_type": t, "source": "registry"} for a, b, t in known])
        self.hidden = pd.DataFrame([{"a_eid": a, "b_eid": b, "link_type": t} for a, b, t in hidden])

        # family_pairs: known predicted-type links as positives; 5 negatives each (half same-province "hard")
        pos = [lk for lk in known if lk[2] in ("PARTNER_OF", "SIBLING_OF")]
        kin = {tuple(sorted(lk[:2])) for lk in self.true_links}
        eids = list(self.persons["eid"])
        prov = dict(zip(self.persons["eid"], self.persons["province"]))
        by_prov = defaultdict(list)
        for e in eids:
            by_prov[prov[e]].append(e)
        rows = []
        for a, b, t in pos:
            rows.append((a, b, t, 1))
            for k in range(5):
                pool = by_prov[prov[a]] if k < 3 else eids
                c = pool[r.integers(len(pool))]
                if c != a and tuple(sorted((a, c))) not in kin:
                    rows.append((a, c, t, 0))
        fam = np.array([self.fam_of[a] for a, *_ in rows])
        fams = np.unique(fam)
        r.shuffle(fams)
        cut1, cut2 = int(0.6 * len(fams)), int(0.8 * len(fams))
        split = {f: ("train" if i < cut1 else "val" if i < cut2 else "test") for i, f in enumerate(fams)}
        df = pd.DataFrame(rows, columns=["a_eid", "b_eid", "link_type", "label"])
        df["split"] = [split[f] for f in fam]
        self.family_pairs = {s: df[df.split == s].drop(columns="split").reset_index(drop=True) for s in ("train", "val", "test")}

        # account labels for the GNN: STR subjects' accounts, temporal split by filing date
        lab = self.strs.merge(self.str_labels, on="str_id")
        lab = lab[lab.subject_eid.str.startswith("P:")]
        rows = [{"account_id": a, "ts": f"{f} 00:00:00", "label": int(y)}
                for s_, f, y in zip(lab.subject_eid, lab.filed_on, lab.is_laundering) for a in self.acct_of[s_]]
        acc = pd.DataFrame(rows).sort_values("ts").drop_duplicates("account_id", keep="last").reset_index(drop=True)
        n = len(acc)
        self.account_labels = {"train": acc.iloc[: int(0.6 * n)], "val": acc.iloc[int(0.6 * n): int(0.8 * n)],
                               "test": acc.iloc[int(0.8 * n):]}

    # ------------------------------------------------------------------ run
    def run(self) -> dict[str, pd.DataFrame]:
        import gc

        gc.disable()   # millions of small dicts: cyclic GC rescans made generation quadratic
        try:
            return self._run()
        finally:
            gc.enable()

    def _run(self) -> dict[str, pd.DataFrame]:
        self.pools()
        self.gen_persons()
        self.gen_companies()
        self.gen_ownership()
        self.plant_structures()
        self.gen_accounts()
        self.gen_transfers()
        self.gen_cases()            # plants slush-fund ownership and minority bank stakes too
        self.normalize_shares()
        self.gen_splits()
        sh = pd.DataFrame([{"owner_eid": o, "owned_eid": c, "share": w, "right_type": "ownership"}
                           for (o, c), w in sorted(self.holds.items())])
        tables = {
            "companies": self.companies, "persons": self.persons, "shareholdings": sh, "roles": self.roles,
            "family_links_known": self.known, "family_links_hidden": self.hidden,
            "accounts": pd.DataFrame(self.accounts_rows),
            "transfers": pd.concat([self.bg_transfers, pd.DataFrame(self.transfers)], ignore_index=True),
            "invoices": pd.concat([self.bg_invoices, pd.DataFrame(self.invoices)], ignore_index=True),
            "loans": pd.DataFrame(self.loans),
            "strs": self.strs, "str_labels": self.str_labels,
            "high_risk_jurisdictions": pd.DataFrame({"country": HIGH_RISK}),
        }
        for s in ("train", "val", "test"):
            tables[f"family_pairs_{s}"] = self.family_pairs[s]
            tables[f"account_labels_{s}"] = self.account_labels[s].reset_index(drop=True)
        return tables


def generate(cfg: GenConfig, out: Path | None = None) -> dict[str, pd.DataFrame]:
    g = Gen(cfg)
    tables = g.run()
    if out is not None:
        write_dir(tables, out)
        counts = {k: len(v) for k, v in tables.items()}
        planted = {k: len(v) for k, v in g.manifest.items() if k != "families"}
        (Path(out) / "manifest.json").write_text(json.dumps(
            {"config": asdict(cfg), "row_counts": counts, "planted_counts": planted,
             "planted": {k: v for k, v in g.manifest.items() if k != "families"}}, indent=1, default=str))
        (Path(out) / "LICENSE.txt").write_text(
            "Synthetic data generated by data/generator/generate.py (CC BY 4.0). No record describes a real\n"
            "person or company. Structures follow: Atzeni et al., EDBT 2020 and KR 2021 workshop; Bellomarini,\n"
            "Laurenza, Sallinger 2020; Weber et al., NeurIPS 2018 workshop (AMLSim-style typologies).\n")
    return tables


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--companies", type=int, default=5000)
    ap.add_argument("--persons", type=int, default=3000)
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--density", choices=list(DENSITY), default="normal")
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--to-snowflake", dest="to_snowflake", help="DB.SCHEMA to load the tables into")
    a = ap.parse_args()
    cfg = GenConfig(seed=a.seed, companies=a.companies, persons=a.persons, days=a.days,
                    density=a.density, holdout=a.holdout)
    tables = generate(cfg, a.out)
    print({k: len(v) for k, v in tables.items()})
    if a.to_snowflake:
        from data.generator.snowflake_load import load_tables
        load_tables(tables, a.to_snowflake)


if __name__ == "__main__":
    main()
