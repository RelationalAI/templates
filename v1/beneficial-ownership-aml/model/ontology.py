"""The core ontology: EDB concepts and relationships (P1 Company Graph, P3 AML KG, P4 transactions).

Derived relationships are added by the stage modules (family, control, ownership, ...), which
attach their handles to the same `Onto` object so later stages and queries can use them.
"""

from types import SimpleNamespace

from relationalai.semantics import DateTime, Float, Integer, Model, String


class Onto(SimpleNamespace):
    """Attribute bag of concept and relationship handles for one model."""


def declare(model: Model) -> Onto:
    o = Onto(model=model)
    C, P, R = model.Concept, model.Property, model.Relationship

    # --- subjects (P1 Def 2.2: companies and persons; Family is derived, P3 Rule 2)
    Entity = C("Entity", identify_by={"eid": String})
    Company = C("Company", extends=[Entity])
    Person = C("Person", extends=[Entity])
    Family = C("Family", extends=[Entity])

    Company.name = P(f"{Company} has name {String:name}")
    Company.legal_form = P(f"{Company} has legal form {String:legal_form}")
    Company.sector = P(f"{Company} in sector {String:sector}")
    Company.province = P(f"{Company} registered in province {String:province}")
    Company.inc_date = P(f"{Company} incorporated on {String:inc_date}")
    Company.is_bank = R(f"{Company} is a bank")

    Person.num = P(f"{Person} has number {Integer:num}")
    Person.first_name = P(f"{Person} has first name {String:first_name}")
    Person.surname = P(f"{Person} has surname {String:surname}")
    Person.sex = P(f"{Person} has sex {String:sex}")
    Person.birth_date = P(f"{Person} born on {String:birth_date}")
    Person.birth_year = P(f"{Person} born in year {Integer:birth_year}")
    Person.birth_city = P(f"{Person} born in city {String:birth_city}")
    Person.address = P(f"{Person} lives at {String:address}")
    Person.province = P(f"{Person} lives in province {String:province}")
    Person.is_pep = R(f"{Person} is a politically exposed person")
    Person.has_record = R(f"{Person} has a criminal record")

    # --- ownership (EDB) and roles
    Entity.owns = P(f"{Entity:owner} owns {Company:owned} with {Float:share}")
    Person.is_ceo_at = R(f"{Person} is CEO at {Company}")

    # --- personal links: known (registry, confidence 1.0) and predicted (VADA-LINK, p > T)
    Person.link = P(f"{Person:a} linked to {Person:b} as {String:link_type} with {Float:confidence}")

    # --- transactions layer (P4)
    Account = C("Account", identify_by={"account_id": String})
    Account.holder_eid = P(f"{Account} registered to holder id {String:holder_eid}")
    Account.holder = P(f"{Account} held by {Entity:holder}")
    Account.bank = P(f"{Account} kept at {Company:bank}")
    Account.country = P(f"{Account} in country {String:country}")
    Account.opened_on = P(f"{Account} opened on {String:opened_on}")

    Transfer = C("Transfer", identify_by={"transfer_id": String})
    Transfer.from_account = P(f"{Transfer} sent from {Account:from_account}")
    Transfer.to_account = P(f"{Transfer} sent to {Account:to_account}")
    Transfer.amount = P(f"{Transfer} has amount {Float:amount}")
    Transfer.ts = P(f"{Transfer} at {DateTime:ts}")
    Transfer.product = P(f"{Transfer} pays for {String:product}")

    Invoice = C("Invoice", identify_by={"invoice_id": String})
    Invoice.issuer = P(f"{Invoice} issued by {Entity:issuer}")
    Invoice.payee = P(f"{Invoice} billed to {Entity:payee}")
    Invoice.product = P(f"{Invoice} bills for {String:product}")
    Invoice.amount = P(f"{Invoice} has amount {Float:amount}")
    Invoice.issued_on = P(f"{Invoice} issued on {String:issued_on}")

    Loan = C("Loan", identify_by={"loan_id": String})
    Loan.applicant = P(f"{Loan} requested by {Person:applicant}")
    Loan.lender = P(f"{Loan} requested from {Company:lender}")
    Loan.amount = P(f"{Loan} has amount {Float:amount}")
    Loan.requested_on = P(f"{Loan} requested on {String:requested_on}")

    # --- suspicious transaction reports (P3 §2.1)
    STR = C("STR", identify_by={"str_id": String})
    STR.num = P(f"{STR} has number {Integer:num}")
    STR.subject = P(f"{STR} is about {Entity:subject}")
    STR.bank = P(f"{STR} filed by {Company:bank}")
    STR.instrument_type = P(f"{STR} reports an instrument of type {String:instrument_type}")
    STR.instrument_id = P(f"{STR} reports instrument {String:instrument_id}")
    STR.amount = P(f"{STR} has amount {Float:amount}")
    STR.filed_on = P(f"{STR} filed on {String:filed_on}")
    STR.loan = P(f"{STR} reports loan {Loan:loan}")
    STR.transfer = P(f"{STR} reports transfer {Transfer:transfer}")

    # --- reference data
    HighRisk = C("HighRiskJurisdiction", identify_by={"country": String})
    Rule = C("Rule", identify_by={"rule_id": String})
    Rule.weight = P(f"{Rule} has weight {Float:weight}")
    Rule.offence = P(f"{Rule} indicates offence {String:offence}")
    Rule.priority = P(f"{Rule} has priority {Integer:priority}")
    Rule.description = P(f"{Rule} is described as {String:description}")
    Analyst = C("Analyst", identify_by={"analyst_id": String})
    Analyst.hours = P(f"{Analyst} has {Float:hours} hours")
    Analyst.skills = P(f"{Analyst} has skills {String:skills}")

    o.__dict__.update(
        Entity=Entity, Company=Company, Person=Person, Family=Family, Account=Account, Transfer=Transfer,
        Invoice=Invoice, Loan=Loan, STR=STR, HighRisk=HighRisk, Rule=Rule, Analyst=Analyst,
    )
    return o
