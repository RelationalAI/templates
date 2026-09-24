"""Stable concepts, properties, and relationships for entity resolution."""

from relationalai.semantics import Float, Integer, Model, String

model = Model("entity_resolution")

Record = model.Concept("Record", identify_by={"record_id": Integer})
Record.source_system = model.Property(f"{Record} has {String:source_system}")
Record.full_name = model.Property(f"{Record} has {String:full_name}")
Record.street = model.Property(f"{Record} has {String:street}")
Record.city = model.Property(f"{Record} has {String:city}")
Record.state = model.Property(f"{Record} has {String:state}")
Record.postal_code = model.Property(f"{Record} has {String:postal_code}")
Record.created_at = model.Property(f"{Record} has {String:created_at}")
Record.coverage_amount = model.Property(f"{Record} has {Float:coverage_amount}")
Record.date_of_birth = model.Property(f"{Record} has {String:date_of_birth}")
Record.gov_id_last4 = model.Property(f"{Record} has {String:gov_id_last4}")
Record.email = model.Property(f"{Record} has {String:email}")
Record.phone = model.Property(f"{Record} has {String:phone}")
Record.entity_key = model.Property(f"{Record} has {Integer:entity_key}")
Record.is_duplicate = model.Relationship(f"{Record} is a duplicate")

CandidateMatch = model.Concept("CandidateMatch", identify_by={"pair_id": Integer})
CandidateMatch.rec_a = model.Relationship(
    f"{CandidateMatch} has first accepted {Record:rec_a}"
)
CandidateMatch.rec_b = model.Relationship(
    f"{CandidateMatch} has second accepted {Record:rec_b}"
)
CandidateMatch.score = model.Property(f"{CandidateMatch} has {Float:score}")
CandidateMatch.confidence_tier = model.Property(
    f"{CandidateMatch} has tier {String:confidence_tier}"
)

ReviewPair = model.Concept("ReviewPair", identify_by={"pair_id": Integer})
ReviewPair.rec_a = model.Relationship(f"{ReviewPair} has first review {Record:rec_a}")
ReviewPair.rec_b = model.Relationship(f"{ReviewPair} has second review {Record:rec_b}")
ReviewPair.score = model.Property(f"{ReviewPair} has {Float:score}")

ResolvedParty = model.Concept("ResolvedParty", identify_by={"key": Integer})
Record.resolved_party = model.Relationship(
    f"{Record} contributes exposure to {ResolvedParty:resolved_party}"
)
ResolvedParty.total_exposure = model.Property(
    f"{ResolvedParty} has {Float:total_exposure}"
)
ResolvedParty.is_over_limit = model.Relationship(
    f"{ResolvedParty} is over the accumulation limit"
)
ResolvedParty.excess = model.Property(f"{ResolvedParty} has {Float:excess}")
ResolvedParty.premium = model.Property(f"{ResolvedParty} has {Float:premium}")
ResolvedParty.cede = model.Property(
    f"{ResolvedParty} cede decision {Float:cede}"
)
