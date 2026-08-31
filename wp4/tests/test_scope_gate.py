"""Test the scope gate and the schemas without calling a model.

These tests cover the two ways it could fail while appearing to work: refusing
everything, which an empty allowlist does quietly, and admitting a fact the
ontology never asserted, which is the fabricated citation the gate exists to
catch.
"""

import pytest

from wp4 import scope_gate
from wp4.schemas import CandidateInstance, EvidenceTriple, ValidationResult

ITEMS = scope_gate.load_items()
ITEM_001 = ITEMS["COMP101-L10-ITEM-001"]  # Explain what a class represents
SCOPE_001 = scope_gate.build_scope(ITEM_001)


# -- the item file -------------------------------------------------------

def test_every_item_parses_and_carries_a_gate():
    assert len(ITEMS) == 51
    assert all(item.ontology_gate.anchor_ids for item in ITEMS.values())


def test_every_relation_id_translates_to_a_real_owl_property():
    """The item file is snake_case, the ontology is camelCase.

    Every one of the relation ids differs this way. If the translation were
    dropped, the gate would allow nothing and reject all evidence in silence,
    so this is the test that keeps the failure loud.
    """
    properties = {
        scope_gate.graph_service._local_name(p)
        for p in scope_gate.graph_service.OBJECT_PROPERTIES
        | scope_gate.graph_service.DATATYPE_PROPERTIES
    }
    used = {
        relation
        for item in ITEMS.values()
        for relation in item.ontology_gate.allowed_relation_ids
    }
    untranslatable = {r for r in used if scope_gate.to_owl_property(r) not in properties}
    assert untranslatable == set()


def test_translation_leaves_an_already_camel_case_name_alone():
    assert scope_gate.to_owl_property("dependsOn") == "dependsOn"
    assert scope_gate.to_owl_property("depends_on") == "dependsOn"
    assert scope_gate.to_owl_property("produces_type") == "producesType"


# -- the scope -----------------------------------------------------------

def test_every_item_resolves_at_least_one_evidence_triple():
    """An item with no evidence cannot ground a single instance."""
    barren = [i.id for i in ITEMS.values() if not scope_gate.build_scope(i).evidence]
    assert barren == []


def test_evidence_never_reaches_outside_the_allowlist():
    """Both ends of every object-property fact must be on the list."""
    for item in ITEMS.values():
        scope = scope_gate.build_scope(item)
        for triple in scope.evidence:
            assert triple.subject in scope.allowed_entities
            assert triple.predicate in scope.allowed_relations


def test_lecture_membership_edges_are_never_evidence():
    """teaches/taughtIn connect everything to the lecture and to each other.

    The item file excludes them for that reason: they are true, and they carry
    no pedagogical information at item level.
    """
    for item in ITEMS.values():
        predicates = {t.predicate for t in scope_gate.build_scope(item).evidence}
        assert "teaches" not in predicates
        assert "taughtIn" not in predicates


def test_building_the_same_scope_twice_gives_the_same_result():
    first = scope_gate.build_scope(ITEM_001)
    second = scope_gate.build_scope(ITEM_001)
    assert first.allowed_entities == second.allowed_entities
    assert first.evidence == second.evidence


# -- the three gate predicates -------------------------------------------

def test_is_entity_allowed():
    assert scope_gate.is_entity_allowed(SCOPE_001, "COOP001")       # Class
    assert not scope_gate.is_entity_allowed(SCOPE_001, "COOP019")   # Duck Typing


def test_is_relation_allowed_accepts_both_spellings():
    assert scope_gate.is_relation_allowed(SCOPE_001, "has_part")
    assert scope_gate.is_relation_allowed(SCOPE_001, "hasPart")
    assert not scope_gate.is_relation_allowed(SCOPE_001, "contrastsWith")


def test_is_evidence_allowed_accepts_a_fact_the_gate_collected():
    assert scope_gate.is_evidence_allowed(SCOPE_001, SCOPE_001.evidence[0])


def test_is_evidence_allowed_rejects_a_fact_the_ontology_never_asserts():
    """The failure mode this whole gate exists to catch.

    Each part below is individually inside the scope, so an allowlist check
    alone would pass it. The triple is still fabricated, and membership of the
    collected evidence is what refuses it.
    """
    invented = EvidenceTriple(
        subject="COOP001", predicate="hasPart", object="PI_OOP03"
    )
    assert invented not in SCOPE_001.evidence
    assert scope_gate.is_entity_allowed(SCOPE_001, invented.subject)
    assert scope_gate.is_entity_allowed(SCOPE_001, invented.object)
    assert scope_gate.is_relation_allowed(SCOPE_001, invented.predicate)
    assert not scope_gate.is_evidence_allowed(SCOPE_001, invented)


def test_is_evidence_allowed_rejects_an_out_of_scope_entity():
    leaked = EvidenceTriple(
        subject="COOP001", predicate="dependsOn", object="COOP019"  # Duck Typing
    )
    assert not scope_gate.is_evidence_allowed(SCOPE_001, leaked)


# -- the output schema ---------------------------------------------------

def test_mcq_requires_choices_containing_the_answer():
    with pytest.raises(ValueError, match="two choices"):
        CandidateInstance(
            item_id="X", instance_type="mcq", prompt="p", answer_key="a"
        )
    with pytest.raises(ValueError, match="one of its choices"):
        CandidateInstance(
            item_id="X", instance_type="mcq", prompt="p",
            answer_key="a", choices=["b", "c"],
        )


def test_a_non_mcq_must_not_carry_choices():
    """A short answer with choices is the wrong question type, not a stray field."""
    with pytest.raises(ValueError, match="must not carry choices"):
        CandidateInstance(
            item_id="X", instance_type="short_answer", prompt="p",
            answer_key="a", choices=["a", "b"],
        )


def test_an_unknown_field_is_malformed_output():
    with pytest.raises(ValueError):
        CandidateInstance(
            item_id="X", instance_type="short_answer", prompt="p",
            answer_key="a", difficulty="hard",
        )


def test_a_validation_result_must_justify_a_failure():
    with pytest.raises(ValueError, match="must say why"):
        ValidationResult(item_id="X", kind="ontology", passed=False)
    with pytest.raises(ValueError, match="cannot list failures"):
        ValidationResult(
            item_id="X", kind="ontology", passed=True, failures=["out of scope"]
        )
