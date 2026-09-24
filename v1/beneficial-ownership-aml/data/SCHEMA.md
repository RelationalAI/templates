# Data contracts

Every table the template reads, as CSV (bundled sample) or as a Snowflake table (same name, upper-case).
Ids carry a type prefix: `C:` company, `P:` person, `A:` account (`F:` families are derived).
Dates are ISO strings (`YYYY-MM-DD`); `ts` is a timestamp. `str?` means optional (may be empty).

Required: companies, persons, shareholdings. Evaluation-only tables are never loaded into the model: account_labels_test, family_links_hidden, str_labels.

## `companies`

Company register. `is_bank` 1 for lenders/banks.

| column | type |
|---|---|
| `eid` | str |
| `name` | str |
| `legal_form` | str |
| `sector` | str |
| `province` | str |
| `inc_date` | date |
| `is_bank` | int |

## `persons`

Person register. `num` is a dense integer id (family keys use min(num)).

| column | type |
|---|---|
| `eid` | str |
| `num` | int |
| `first_name` | str |
| `surname` | str |
| `sex` | str |
| `birth_date` | date |
| `birth_year` | int |
| `birth_city` | str |
| `address` | str |
| `province` | str |
| `is_pep` | int |
| `has_record` | int |

## `shareholdings`

Who owns what share of which company. Only `right_type = ownership` is used. Unique per (owner, owned, right_type); share in (0, 1].

| column | type |
|---|---|
| `owner_eid` | str |
| `owned_eid` | str |
| `share` | float |
| `right_type` | str |

## `roles`

Company roles; `CEO` feeds P3 Rule 7 (the CEO is treated as holding 1.0).

| column | type |
|---|---|
| `person_eid` | str |
| `company_eid` | str |
| `role` | str |

## `family_links_known`

Personal links from registries (spouse, sibling, parent). Confidence 1.0.

| column | type |
|---|---|
| `a_eid` | str |
| `b_eid` | str |
| `link_type` | str |
| `source` | str |

## `family_links_hidden`

Evaluation only: true links withheld from the registry, to be recovered by VADA-LINK.

| column | type |
|---|---|
| `a_eid` | str |
| `b_eid` | str |
| `link_type` | str |

## `family_pairs_train`

Labeled person pairs for calibrating the family-link classifier (and training the GNN).

| column | type |
|---|---|
| `a_eid` | str |
| `b_eid` | str |
| `link_type` | str |
| `label` | int |

## `family_pairs_val`

Labeled pairs for choosing link thresholds.

| column | type |
|---|---|
| `a_eid` | str |
| `b_eid` | str |
| `link_type` | str |
| `label` | int |

## `family_pairs_test`

Labeled pairs held out for evaluation.

| column | type |
|---|---|
| `a_eid` | str |
| `b_eid` | str |
| `link_type` | str |
| `label` | int |

## `accounts`

Bank accounts. `holder_eid` may reference an entity missing from the registers (unknown counterparty).

| column | type |
|---|---|
| `account_id` | str |
| `holder_eid` | str |
| `bank_eid` | str |
| `country` | str |
| `opened_on` | date |

## `transfers`

Money transfers. `product` (optional) is set for business payments and matched against invoices.

| column | type |
|---|---|
| `transfer_id` | str |
| `from_account` | str |
| `to_account` | str |
| `amount` | float |
| `ts` | datetime |
| `product` | str? |

## `invoices`

Invoices issued by `issuer_eid` to `payee_eid` (P3 slush-fund rules).

| column | type |
|---|---|
| `invoice_id` | str |
| `issuer_eid` | str |
| `payee_eid` | str |
| `product` | str |
| `amount` | float |
| `issued_on` | date |

## `loans`

Loan applications.

| column | type |
|---|---|
| `loan_id` | str |
| `applicant_eid` | str |
| `lender_eid` | str |
| `amount` | float |
| `requested_on` | date |

## `strs`

Suspicious transaction reports. `instrument_id` points to a loan or transfer.

| column | type |
|---|---|
| `str_id` | str |
| `num` | int |
| `subject_eid` | str |
| `bank_eid` | str |
| `instrument_type` | str |
| `instrument_id` | str |
| `amount` | float |
| `filed_on` | date |

## `str_labels`

Evaluation only: ground truth for synthetic STRs.

| column | type |
|---|---|
| `str_id` | str |
| `is_laundering` | int |
| `offence` | str |

## `account_labels_train`

GNN account classifier labels (time-ordered split).

| column | type |
|---|---|
| `account_id` | str |
| `ts` | datetime |
| `label` | int |

## `account_labels_val`

GNN account classifier labels (time-ordered split).

| column | type |
|---|---|
| `account_id` | str |
| `ts` | datetime |
| `label` | int |

## `account_labels_test`

Evaluation only.

| column | type |
|---|---|
| `account_id` | str |
| `ts` | datetime |
| `label` | int |

## `high_risk_jurisdictions`

Country codes treated as high-risk (illustrative list; replace with your policy).

| column | type |
|---|---|
| `country` | str |

## `rule_catalog`

Weight, offence class and priority of every AML pattern rule (tunable without code).

| column | type |
|---|---|
| `rule_id` | str |
| `weight` | float |
| `offence` | str |
| `priority` | int |
| `description` | str |

## `analysts`

Analyst capacity (hours) and skills for the triage assign mode.

| column | type |
|---|---|
| `analyst_id` | str |
| `hours` | float |
| `skills` | str |
