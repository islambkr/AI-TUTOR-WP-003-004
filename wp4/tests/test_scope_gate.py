"""Test the scope gate and the schemas without calling a model.

These tests cover the two ways it could fail while appearing to work: refusing
everything, which an empty allowlist does quietly, and admitting a fact the
ontology never asserted, which is the fabricated citation the gate exists to
catch.
"""

import pytest

from wp4 import scope_gate
from wp4.schemas import (
    CANDIDATE_INSTANCE,
    EvidenceTriple,
    MCQInstance,
    OntologyGate,
    ShortAnswerInstance,
    TrueFalseInstance,
    ValidationResult,
)

ITEMS = scope_gate.load_items()
ITEM_001 = ITEMS["COMP101-L10-ITEM-001"]  # Explain what a class represents
SCOPE_001 = scope_gate.build_scope(ITEM_001)


# -- the item file -------------------------------------------------------

def test_every_item_parses_and_carries_a_gate():
    """Parsing is the assertion: `extra="forbid"` means a field nobody modelled
    fails here rather than being dropped in silence, which is how the item
    file's `evidence_triples` went unnoticed in the first version."""
    assert len(ITEMS) == 51
    assert all(item.ontology_gate.allowed_entity_ids for item in ITEMS.values())


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


def test_max_depth_is_bounded():
    """A hand-edited file cannot ask for a traversal nobody intended."""
    with pytest.raises(ValueError, match="less than or equal to 5"):
        OntologyGate(anchor_ids=["A"], allowed_entity_ids=[],
                     allowed_relation_ids=[], max_depth=9)
    with pytest.raises(ValueError, match="at least 1 item"):
        OntologyGate(anchor_ids=[], allowed_entity_ids=[], allowed_relation_ids=[])


def test_an_allowed_relation_implies_its_inverse():
    """The mentor's ruling: for a given relation, assume its opposite as well.

    ITEM-043 permits `is_used_by` only, and the gate now allows `usesConcept`
    with it, because `owl:inverseOf` makes them one edge seen from two ends.
    """
    scope = scope_gate.build_scope(ITEMS["COMP101-L10-ITEM-043"])
    assert "isUsedBy" in scope.allowed_relations
    assert "usesConcept" in scope.allowed_relations


def test_expanding_inverses_does_not_reach_the_lecture_edges():
    """`teaches`/`taughtIn` are an inverse pair, so the expansion could have
    reintroduced them. No item allows either, and adding the partner of a
    relation that is absent adds nothing."""
    assert scope_gate.with_inverses({"teaches"}) == {"teaches", "taughtIn"}
    for item in ITEMS.values():
        allowed = scope_gate.build_scope(item).allowed_relations
        assert "teaches" not in allowed and "taughtIn" not in allowed


def test_a_symmetric_relation_gains_no_partner():
    """contrastsWith is owl:SymmetricProperty, not half of an inverse pair."""
    assert scope_gate.with_inverses({"contrastsWith"}) == {"contrastsWith"}


def test_no_item_declares_a_triple_the_gate_cannot_collect():
    """Once inverses are implied, the direction mismatch disappears.

    Before the ruling, five items cited a triple in the direction opposite to
    their own allowlist and this returned ten of them. compare_declared_evidence
    is kept because it still catches the case it was written for: a file citing
    something asserted in *neither* direction, which would come back with
    `collected=None`.
    """
    for item in ITEMS.values():
        assert scope_gate.compare_declared_evidence(item) == []


def test_comparison_still_catches_a_triple_asserted_in_neither_direction():
    item = ITEMS["COMP101-L10-ITEM-001"]
    invented = item.model_copy(deep=True)
    invented.ontology_gate.evidence_triples = [("COOP001", "has_part", "PI_OOP03")]
    mismatches = scope_gate.compare_declared_evidence(invented)
    assert len(mismatches) == 1
    assert mismatches[0].collected is None


def test_comparing_accepts_a_prebuilt_scope():
    scope = scope_gate.build_scope(ITEMS["COMP101-L10-ITEM-024"])
    assert scope_gate.compare_declared_evidence(
        ITEMS["COMP101-L10-ITEM-024"], scope
    ) == scope_gate.compare_declared_evidence(ITEMS["COMP101-L10-ITEM-024"])


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

def test_the_discriminator_selects_the_variant():
    """`instance_type` alone decides which model the payload is checked against."""
    short = CANDIDATE_INSTANCE.validate_python(
        {"item_id": "X", "instance_type": "short_answer", "prompt": "p",
         "answer_key": "a"}
    )
    mcq = CANDIDATE_INSTANCE.validate_python(
        {"item_id": "X", "instance_type": "mcq", "prompt": "p",
         "answer_key": "a", "choices": ["a", "b"]}
    )
    assert isinstance(short, ShortAnswerInstance)
    assert isinstance(mcq, MCQInstance)


def test_mcq_requires_two_choices_containing_the_answer():
    with pytest.raises(ValueError, match="at least 2 items"):
        MCQInstance(item_id="X", instance_type="mcq", prompt="p",
                    answer_key="a", choices=["a"])
    with pytest.raises(ValueError, match="one of its choices"):
        MCQInstance(item_id="X", instance_type="mcq", prompt="p",
                    answer_key="a", choices=["b", "c"])


def test_mcq_choices_must_be_distinct():
    """Two identical choices are one choice, and duplicating the answer makes
    two of them correct."""
    with pytest.raises(ValueError, match="distinct"):
        MCQInstance(item_id="X", instance_type="mcq", prompt="p",
                    answer_key="a", choices=["a", "a"])


def test_true_false_answers_are_only_true_or_false():
    """The reason the three types are separate models rather than one."""
    assert TrueFalseInstance(item_id="X", instance_type="true_false",
                             prompt="p", answer_key="true").answer_key == "true"
    with pytest.raises(ValueError):
        TrueFalseInstance(item_id="X", instance_type="true_false",
                          prompt="p", answer_key="maybe, it depends")


def test_a_short_answer_has_no_choices_field_at_all():
    """The variant cannot hold choices, so the schema rejects it, not a validator."""
    with pytest.raises(ValueError, match="[Ee]xtra"):
        ShortAnswerInstance(item_id="X", instance_type="short_answer", prompt="p",
                            answer_key="a", choices=["a", "b"])


def test_an_unknown_field_is_malformed_output():
    with pytest.raises(ValueError, match="[Ee]xtra"):
        CANDIDATE_INSTANCE.validate_python(
            {"item_id": "X", "instance_type": "short_answer", "prompt": "p",
             "answer_key": "a", "difficulty": "hard"}
        )


def test_an_unknown_instance_type_is_rejected():
    with pytest.raises(ValueError):
        CANDIDATE_INSTANCE.validate_python(
            {"item_id": "X", "instance_type": "essay", "prompt": "p",
             "answer_key": "a"}
        )


def test_a_validation_result_must_justify_a_failure():
    with pytest.raises(ValueError, match="must say why"):
        ValidationResult(item_id="X", kind="ontology", passed=False)
    with pytest.raises(ValueError, match="cannot list failures"):
        ValidationResult(
            item_id="X", kind="ontology", passed=True, failures=["out of scope"]
        )
