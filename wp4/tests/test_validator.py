"""The deliberate failure cases of WP-004 section 10.8, plus the per-type rules.

Section 10.8 lists eight failures the pipeline must handle. They do not all
belong to the same validator, and saying which is which is the point of section
10.5 and 10.6 being separate steps:

    out-of-scope concept in the prompt      deterministic  -- here
    out-of-scope concept in the answer      deterministic  -- here
    the evidence triple does not exist      deterministic  -- here
    an MCQ has two correct answers          deterministic  -- here, partly
    malformed structured output             deterministic  -- here
    the instance tests the wrong item       deterministic only when the item id
                                            is wrong; a right id on a question
                                            about something else is a judgement
    the instance is trivial                 judgement -- pedagogical validation
    an MCQ distractor is obviously invalid  judgement -- pedagogical validation

The three judgements are asserted here to be *accepted* by the ontology
validator, because claiming otherwise would be claiming a deterministic check
can do something it cannot.
"""

import pytest

from wp4 import scope_gate, validator
from wp4.schemas import MCQInstance, ShortAnswerInstance, TrueFalseInstance

ITEMS = scope_gate.load_items()
ITEM = ITEMS["COMP101-L10-ITEM-001"]  # Explain what a class represents
SCOPE = scope_gate.build_scope(ITEM)
TRIPLE = SCOPE.evidence[0]


def short_answer(**overrides):
    payload = dict(
        item_id=ITEM.id,
        instance_type="short_answer",
        prompt="What does a class define?",
        # Singular "object" on purpose. The plural used to hide the label
        # false-positive described in _names_entity: with a case-insensitive
        # match this line flagged Object (COOP002) as leakage.
        answer_key="A Class defines the attributes and methods of an object.",
        ontology_entities_used=["COOP001"],
        ontology_evidence=[TRIPLE],
    )
    return ShortAnswerInstance(**{**payload, **overrides})


def check(candidate):
    return validator.validate_candidate(candidate, ITEM, SCOPE)


# -- the supported baseline ----------------------------------------------

def test_a_supported_candidate_passes():
    result = check(short_answer())
    assert result.passed, result.failures
    assert result.kind == "ontology"


# -- 10.8: the deterministic failures ------------------------------------

def test_out_of_scope_concept_in_the_prompt():
    result = check(short_answer(prompt="How does Duck Typing relate to a class?"))
    assert not result.passed
    assert any("Duck Typing" in f for f in result.failures)


def test_out_of_scope_concept_in_the_answer():
    result = check(short_answer(answer_key="A Class supports Duck Typing."))
    assert not result.passed
    assert any("answer_key" in f and "Duck Typing" in f for f in result.failures)


def test_a_fabricated_evidence_triple_is_rejected():
    """Each part is allowed; the ontology never asserts the whole."""
    from wp4.schemas import EvidenceTriple

    invented = EvidenceTriple(subject="COOP001", predicate="hasPart", object="PI_OOP03")
    result = check(short_answer(ontology_evidence=[invented]))
    assert not result.passed
    assert any("not asserted" in f for f in result.failures)


def test_an_entity_outside_the_allowlist_is_rejected():
    result = check(short_answer(ontology_entities_used=["COOP019"]))
    assert not result.passed
    assert any("outside the scope" in f for f in result.failures)


def test_malformed_output_is_a_failure_not_an_exception():
    """The generator will produce some; they belong in the dataset with a reason."""
    result = validator.validate_payload(
        {"item_id": ITEM.id, "instance_type": "essay", "prompt": "p",
         "answer_key": "a"},
        ITEM, SCOPE,
    )
    assert not result.passed
    assert any("malformed output" in f for f in result.failures)


def test_an_mcq_with_two_identical_answers_cannot_be_built():
    """"Two correct answers" in its clearest form: the schema refuses it."""
    with pytest.raises(ValueError, match="distinct"):
        MCQInstance(
            item_id=ITEM.id, instance_type="mcq", prompt="Which is a class?",
            answer_key="Class", choices=["Class", "Class"],
        )


def test_an_instance_carrying_the_wrong_item_id_is_rejected():
    result = validator.validate_candidate(
        short_answer(), ITEMS["COMP101-L10-ITEM-013"]
    )
    assert not result.passed
    assert any("item id" in f for f in result.failures)


# -- 10.8: the failures a deterministic check cannot catch ----------------

def test_a_trivial_instance_still_passes_ontology_validation():
    """Triviality is a judgement. Recording that here keeps the two steps honest.

    "Is a Class a class?" is grounded, in scope, correctly cited -- and
    worthless. Only pedagogical validation can say so.
    """
    result = check(short_answer(
        prompt="Is a Class a class?", answer_key="Yes, a Class is a class."
    ))
    assert result.passed, result.failures


def test_an_instance_testing_the_wrong_item_can_still_pass():
    """Right item id, wrong subject. The ontology check has nothing to catch.

    Metaclass is inside ITEM-001's scope, so a question entirely about
    metaclasses is supported, in scope, and not what the item asked for.
    """
    result = check(short_answer(
        prompt="What is a Metaclass?",
        answer_key="A Metaclass (PI_OOP03) is the class of a class.",
        ontology_entities_used=["PI_OOP03"],
    ))
    assert result.passed, result.failures


# -- the per-type answer rules -------------------------------------------

def test_a_short_answer_must_cite_evidence():
    result = check(short_answer(ontology_evidence=[]))
    assert not result.passed
    assert any("at least one evidence triple" in f for f in result.failures)


def test_a_short_answer_naming_nothing_in_scope_fails():
    result = check(short_answer(answer_key="It is a general programming idea."))
    assert not result.passed
    assert any("names no entity in scope" in f for f in result.failures)


def test_a_true_false_answer_is_never_asked_to_carry_ontology_content():
    """The statement is checked, not the word "true" -- see validator docstring."""
    result = validator.validate_candidate(
        TrueFalseInstance(
            item_id=ITEM.id, instance_type="true_false",
            prompt="A Class defines the attributes of its objects.",
            answer_key="true",
            ontology_entities_used=["COOP001"], ontology_evidence=[TRIPLE],
        ),
        ITEM, SCOPE,
    )
    assert result.passed, result.failures


def test_a_true_false_statement_naming_nothing_in_scope_fails():
    result = validator.validate_candidate(
        TrueFalseInstance(
            item_id=ITEM.id, instance_type="true_false",
            prompt="Programming is difficult.", answer_key="true",
            ontology_evidence=[TRIPLE],
        ),
        ITEM, SCOPE,
    )
    assert not result.passed
    assert any("names no entity in scope" in f for f in result.failures)


def test_an_invented_distractor_is_recorded_not_rejected():
    """Mentor decision: let the model write distractors, then compare the 16
    items carrying a `contrasts_with` edge against the 35 without.

    Rejecting every invented distractor would give those 35 a near-zero MCQ
    pass rate by construction, and the comparison would measure this validator
    rather than the worth of the edge. So an ungrounded distractor is counted
    for section 11 and left to the model reviewer of section 10.6.
    """
    candidate = MCQInstance(
        item_id=ITEM.id, instance_type="mcq",
        prompt="Which defines the attributes of its objects?",
        answer_key="Class", choices=["Class", "a sandwich"],
        ontology_entities_used=["COOP001"], ontology_evidence=[TRIPLE],
    )
    result = validator.validate_candidate(candidate, ITEM, SCOPE)
    assert result.passed, result.failures
    assert validator.ungrounded_distractors(candidate, SCOPE) == ["a sandwich"]


def test_an_mcq_answer_still_has_to_be_grounded():
    """Only the distractors were freed; the answer must name something in scope."""
    result = validator.validate_candidate(
        MCQInstance(
            item_id=ITEM.id, instance_type="mcq", prompt="Which one?",
            answer_key="a sandwich", choices=["a sandwich", "a bicycle"],
            ontology_entities_used=["COOP001"], ontology_evidence=[TRIPLE],
        ),
        ITEM, SCOPE,
    )
    assert not result.passed
    assert any("answer names no entity in scope" in f for f in result.failures)


# -- the leakage helper --------------------------------------------------

def test_leakage_matches_whole_words_only():
    """Without word boundaries "Class" matches inside "Metaclass"."""
    assert validator.leaked_entities("A Metaclass is involved.", SCOPE) == []
    assert validator.leaked_entities("Inheritance is involved.", SCOPE) != []


def test_leakage_ignores_concepts_the_ontology_never_heard_of():
    """A prompt about recursion is not leakage; the ontology has no recursion."""
    assert validator.leaked_entities("This involves recursion.", SCOPE) == []


def test_a_lowercase_common_noun_is_not_a_leak():
    """The defect this check nearly shipped with.

    Object is out of scope for 48 of the 51 items and Class for 41, and both are
    ordinary words. Matched case-insensitively, 27 of the mentor's own item
    descriptions were flagged as scope leakage -- the check firing on the very
    text the generator is told to write questions from.
    """
    assert validator.leaked_entities("methods of an object", SCOPE) == []
    assert validator.leaked_entities("an Object holds state", SCOPE) != []


def test_a_multiword_label_still_matches_in_any_case():
    """Duck Typing cannot be confused with prose, so it keeps the loose match."""
    assert validator.leaked_entities("uses duck typing", SCOPE) != []


def test_no_mentor_item_description_leaks_a_common_noun():
    """The measurement that justifies the rule, kept as a test.

    Two of the 51 remain, and both are real: ITEM-030's description names
    __init__ and ITEM-046's names super(), neither of which is on its own
    allowlist. Those are worth raising about the item file, not silencing here.
    """
    flagged = {
        item.id: validator.leaked_entities(
            item.description, scope_gate.build_scope(item)
        )
        for item in ITEMS.values()
        if validator.leaked_entities(item.description, scope_gate.build_scope(item))
    }
    assert sorted(flagged) == ["COMP101-L10-ITEM-030", "COMP101-L10-ITEM-046"]


def test_an_out_of_scope_distractor_is_reported_as_leakage():
    """Not as "names no entity" -- it plainly names one, just the wrong one."""
    result = validator.validate_candidate(
        MCQInstance(
            item_id=ITEM.id, instance_type="mcq",
            prompt="Which defines the attributes of its objects?",
            answer_key="Class", choices=["Class", "Duck Typing"],
            ontology_entities_used=["COOP001"], ontology_evidence=[TRIPLE],
        ),
        ITEM, SCOPE,
    )
    assert not result.passed
    assert any("choice 2" in f and "Duck Typing" in f for f in result.failures)
    assert not any("names no entity" in f for f in result.failures)
