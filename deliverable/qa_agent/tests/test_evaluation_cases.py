"""Check the evaluation set itself against the ontology.

report.md section 4.6 records a defect that the evaluation could not catch: the
expectations were produced with graph_service, so a bug in the service wrote
itself into the expected answers and then passed. Case 15 expected the reverse
of what the ontology asserts.

These tests read the RDF file directly with rdflib and never call
graph_service, so the same class of defect fails here.
"""

import sys
from pathlib import Path

import rdflib
from rdflib.namespace import RDFS

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation import CASES  # noqa: E402

ONTOLOGY = rdflib.Graph().parse(
    Path(__file__).parent.parent / "comp101_L10.owl", format="xml"
)
OOP = rdflib.Namespace("http://comp101.sase.um6p.ma/ontology/oop#")


def _iri_of(name: str):
    """Find an entity by rdfs:label or courseId, using rdflib alone."""
    for predicate in (RDFS.label, OOP.courseId):
        for subject in ONTOLOGY.subjects(predicate, rdflib.Literal(name)):
            return subject
    raise AssertionError(f"no entity labelled {name!r} in the ontology")


def _asserted_answers(entity: str, relation: str) -> set[str]:
    """Everything satisfying "entity relation ?x", read straight from the triples.

    An asserted inverse counts, because owl:inverseOf makes it the same fact --
    but the entity must sit in the subject position of the relation asked about.
    """
    subject = _iri_of(entity)
    prop = OOP[relation]
    inverse = ONTOLOGY.value(prop, rdflib.OWL.inverseOf) or ONTOLOGY.value(
        predicate=rdflib.OWL.inverseOf, object=prop
    )

    others = set(ONTOLOGY.objects(subject, prop))
    if inverse is not None:
        others |= set(ONTOLOGY.subjects(inverse, subject))

    answers = set()
    for other in others:
        answers.add(str(ONTOLOGY.value(other, RDFS.label)))
        course_id = ONTOLOGY.value(other, OOP.courseId)
        if course_id is not None:
            answers.add(str(course_id))
    return answers


CASES_WITH_TRUTH = [case for case in CASES if "truth" in case]


def test_every_relation_case_declares_its_ground_truth():
    """A relation case without a truth field cannot be checked against triples."""
    unchecked = [
        case["id"]
        for case in CASES
        if case["category"] == "relation" and "truth" not in case
    ]
    assert unchecked == [], f"relation cases missing truth: {unchecked}"


def test_evaluation_expectations_match_the_raw_triples():
    """Every expected string must be a real answer to the case's own question.

    This is the check that would have caught the 4.6 defect: case 15 expected
    Polymorphism for "what enables Method Overriding", which the triples do not
    support in that direction.
    """
    for case in CASES_WITH_TRUTH:
        entity, relation = case["truth"]
        answers = _asserted_answers(entity, relation)
        for phrase in case.get("expect", []):
            if phrase == entity or phrase in ("no", "none", "not", "nothing"):
                continue  # the entity's own name, or a negation for empty cases
            assert phrase in answers, (
                f"case {case['id']}: expected {phrase!r}, but the ontology's "
                f"answer to '{entity} {relation} ?' is {sorted(answers) or 'nothing'}"
            )


def test_forbidden_strings_are_genuinely_wrong_answers():
    """A forbidden string must not be a correct answer to the same question."""
    for case in CASES_WITH_TRUTH:
        entity, relation = case["truth"]
        answers = _asserted_answers(entity, relation)
        for phrase in case.get("forbid", []):
            assert phrase not in answers, (
                f"case {case['id']}: forbids {phrase!r}, which IS a correct "
                f"answer to '{entity} {relation} ?'"
            )


def test_empty_result_cases_really_have_no_answer():
    """Cases asserting "nothing recorded" must be backed by an empty triple set."""
    for case in CASES_WITH_TRUTH:
        if case["category"] != "empty-result":
            continue
        entity, relation = case["truth"]
        assert _asserted_answers(entity, relation) == set(), (
            f"case {case['id']} expects no answer, but the ontology has one"
        )
