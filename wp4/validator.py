"""validator.py -- Step 6 of WP-004: deterministic ontology validation.

This module decides whether a candidate is *supported*, never whether it is
*good*. Those are different questions and the work package requires them to stay
apart: everything here is a set membership test or a string search, so the same
candidate always gets the same verdict, and no model is consulted. Judgements
about triviality, wording and difficulty belong to pedagogical validation and
are marked as model judgements when they arrive.

The six checks required by section 10.5:

    the item identifier exists              validate_candidate(..., item=...)
    the output schema is valid              validate_payload
    every used entity is allowed            _entities_are_allowed
    every used relation is allowed          _relations_are_allowed
    every cited evidence triple exists      _evidence_is_supported
    the answer key has ontology support     _answer_is_supported

The last one is the only one the work package leaves open, and it cannot be one
rule: an MCQ answer is usually an entity, a short answer is prose, and a
true/false answer is the word "true" or "false" and carries no ontology content
at all. A single rule either fails every true/false candidate or is vacuous, so
each variant is checked on its own terms. 
"""

import re

from pydantic import ValidationError

from . import scope_gate
from .schemas import (
    CANDIDATE_INSTANCE,
    CandidateInstance,
    Item,
    MCQInstance,
    OntologyScope,
    ShortAnswerInstance,
    TrueFalseInstance,
    ValidationResult,
)


def _all_labels() -> dict[str, str]:
    """courseId -> rdfs:label for every individual in the ontology.

    Resolved once. It was previously rebuilt on every call, which meant walking
    the graph twice per candidate for a mapping that cannot change.
    """
    labels = {}
    for course_id in {
        str(o)
        for o in scope_gate.graph_service.GRAPH.objects(
            None, scope_gate.graph_service.OOP.courseId
        )
    }:
        iri = scope_gate._entity_iri(course_id)
        labels[course_id] = (
            scope_gate.graph_service._label_of(iri) if iri is not None else ""
        )
    return labels


LABELS: dict[str, str] = _all_labels()
ALL_COURSE_IDS: frozenset[str] = frozenset(LABELS)


def _names_entity(text: str, course_id: str) -> bool:
    """Does this text name that entity, by identifier or by label?

    Identifiers match case-insensitively: COOP001 is distinctive enough that a
    match is never accidental.

    Labels are the difficult half, because most of them are ordinary OOP nouns.
    A single alphabetic label -- Object, Class, Inheritance -- is matched
    *case-sensitively*, because writers use lowercase "object" generically and
    capitalise "Object" when they mean the ontology entity. Matching those
    case-insensitively flagged 27 of the 51 mentor-approved item descriptions as
    scope leakage, including descriptions whose own item is about objects: the
    check fired on exactly the text it exists to accept.

    Multi-word labels and labels containing non-letters -- Duck Typing,
    __init__, super() -- keep the case-insensitive match. They cannot be
    confused with ordinary prose, so the looser rule costs nothing there.

    This trades false positives for false negatives, which is the right
    direction for a check that rejects work: a missed leak reaches the model
    reviewer of section 10.6, whereas a false positive silently discards a
    correct candidate and would dominate section 11's scope-violation rate.
    """
    if re.search(rf"(?<!\w){re.escape(course_id)}(?!\w)", text, re.IGNORECASE):
        return True

    label = LABELS.get(course_id, "")
    if not label:
        return False

    flags = 0 if label.isalpha() else re.IGNORECASE
    return re.search(rf"(?<!\w){re.escape(label)}(?!\w)", text, flags) is not None


def names_an_allowed_entity(text: str, scope: OntologyScope) -> bool:
    """True when the text names at least one entity the gate permits."""
    return any(_names_entity(text, cid) for cid in scope.allowed_entities)


def leaked_entities(text: str, scope: OntologyScope) -> list[str]:
    """Entities of the ontology that appear in the text but are out of scope.

    This is the scope-leakage check of section 10.8. It is deliberately limited
    to entities the ontology knows about: a prompt mentioning "recursion" is not
    caught here, because the ontology has no opinion on recursion, and inventing
    one would make this check a judgement rather than a lookup.
    """
    return [
        f"{LABELS[cid]} ({cid})" if LABELS.get(cid) else cid
        for cid in sorted(ALL_COURSE_IDS - scope.allowed_entities)
        if _names_entity(text, cid)
    ]


def _entities_are_allowed(candidate: CandidateInstance, scope: OntologyScope) -> list[str]:
    return [
        f"entity {e} is outside the scope of {scope.item_id}"
        for e in candidate.ontology_entities_used
        if not scope_gate.is_entity_allowed(scope, e)
    ]


def _relations_are_allowed(candidate: CandidateInstance, scope: OntologyScope) -> list[str]:
    return [
        f"relation {t.predicate} is not allowed for {scope.item_id}"
        for t in candidate.ontology_evidence
        if not scope_gate.is_relation_allowed(scope, t.predicate)
    ]


def _evidence_is_supported(candidate: CandidateInstance, scope: OntologyScope) -> list[str]:
    """Every cited triple must be one the gate actually collected.

    A triple whose three parts are each allowed but which the ontology never
    asserts is a fabricated citation, and this is the check that refuses it.
    """
    return [
        f"evidence not asserted in the ontology: {t}"
        for t in candidate.ontology_evidence
        if not scope_gate.is_evidence_allowed(scope, t)
    ]


def _answer_is_supported(candidate: CandidateInstance, scope: OntologyScope) -> list[str]:
    """Per-variant, because the three types put their content in different places.

    MCQ -- only the *answer* must name an allowed entity. Distractors are not
    required to, by mentor decision: they are to be written by the model, and
    the point of the exercise is to compare the 16 items with a `contrasts_with`
    edge against the 35 without, to see what that edge is worth. A rule
    rejecting every invented distractor would give those 35 items a near-zero
    MCQ pass rate by construction, and the comparison would measure this
    function instead of the ontology.

    Section 10.6 lists "distractors are plausible but incorrect" under
    pedagogical validation, which is where the judgement belongs. What stays
    deterministic is leakage: a choice naming an out-of-scope entity is still
    refused by validate_candidate, because that is a lookup rather than an
    opinion. A choice naming no ontology entity at all is recorded as a signal
    on the candidate record for section 11, not as a rejection.

    Short answer -- prose, so it is checked for naming an allowed entity rather
    than for matching one, and it must cite at least one triple. Requiring a
    verbatim label would fail every well-written paraphrase.

    True or false -- the answer is a single word and can never carry ontology
    content, so the *prompt* is what must be supported. Checking the answer here
    would fail every true/false candidate and make the pass rate meaningless.
    """
    problems = []

    if isinstance(candidate, MCQInstance):
        if not names_an_allowed_entity(candidate.answer_key, scope):
            problems.append("the answer names no entity in scope")

    elif isinstance(candidate, ShortAnswerInstance):
        if not names_an_allowed_entity(candidate.answer_key, scope):
            problems.append("the answer names no entity in scope")
        if not candidate.ontology_evidence:
            problems.append("a short answer must cite at least one evidence triple")

    elif isinstance(candidate, TrueFalseInstance):
        if not names_an_allowed_entity(candidate.prompt, scope):
            problems.append("the statement names no entity in scope")
        if not candidate.ontology_evidence:
            problems.append("a true/false statement must cite the evidence it rests on")

    return problems


def validate_candidate(
    candidate: CandidateInstance,
    item: Item,
    scope: OntologyScope | None = None,
) -> ValidationResult:
    """The deterministic verdict on one parsed candidate."""
    scope = scope_gate.build_scope(item) if scope is None else scope
    problems: list[str] = []

    if candidate.item_id != item.id:
        problems.append(f"item id {candidate.item_id!r} is not {item.id!r}")

    problems += _entities_are_allowed(candidate, scope)
    problems += _relations_are_allowed(candidate, scope)
    problems += _evidence_is_supported(candidate, scope)
    problems += _answer_is_supported(candidate, scope)

    texts = [("prompt", candidate.prompt), ("answer_key", candidate.answer_key)]
    texts += [
        (f"choice {n}", choice)
        for n, choice in enumerate(getattr(candidate, "choices", None) or [], 1)
    ]
    for where, text in texts:
        for leak in leaked_entities(text, scope):
            problems.append(f"out-of-scope entity in the {where}: {leak}")

    return ValidationResult(
        item_id=item.id,
        kind="ontology",
        passed=not problems,
        failures=problems,
    )


def ungrounded_distractors(
    candidate: CandidateInstance, scope: OntologyScope
) -> list[str]:
    """Choices naming no ontology entity at all -- a signal, not a failure.

    Reported for section 11 alongside the verdict rather than inside it: by
    mentor decision distractors may be invented by the model, so this counts
    how often that happens without rejecting the candidate for it. Comparing
    the rate across the 16 items with a `contrasts_with` edge and the 35
    without is the experiment the mentor asked for.
    """
    if not isinstance(candidate, MCQInstance):
        return []
    return [
        choice
        for choice in candidate.choices
        if choice != candidate.answer_key
        and not names_an_allowed_entity(choice, scope)
        and not leaked_entities(choice, scope)
    ]


def validate_payload(
    payload: dict, item: Item, scope: OntologyScope | None = None
) -> ValidationResult:
    """Parse an untrusted record, then validate it.

    Malformed output is an ontology failure like any other rather than an
    exception the caller has to catch: the generator will produce some, and they
    belong in the dataset with a reason attached, not in a traceback.
    """
    try:
        candidate = CANDIDATE_INSTANCE.validate_python(payload)
    except ValidationError as error:
        return ValidationResult(
            item_id=item.id,
            kind="ontology",
            passed=False,
            failures=[f"malformed output: {e['loc']} {e['msg']}" for e in error.errors()],
        )
    return validate_candidate(candidate, item, scope)


def main() -> None:
    items = scope_gate.load_items()
    item = items["COMP101-L10-ITEM-001"]
    scope = scope_gate.build_scope(item)

    good = {
        "item_id": item.id,
        "instance_type": "short_answer",
        "prompt": "What does a class define?",
        "answer_key": "A Class defines the attributes and methods of its objects.",
        "ontology_entities_used": ["COOP001"],
        "ontology_evidence": [scope.evidence[0].model_dump()],
    }
    leaking = {**good, "prompt": "How does Duck Typing relate to a class?"}
    fabricated = {
        **good,
        "ontology_evidence": [
            {"subject": "COOP001", "predicate": "hasPart", "object": "PI_OOP03"}
        ],
    }

    for name, payload in [
        ("supported", good),
        ("scope leakage", leaking),
        ("fabricated evidence", fabricated),
        ("malformed", {**good, "instance_type": "essay"}),
    ]:
        result = validate_payload(payload, item, scope)
        print(f"{name:<22} {'pass' if result.passed else 'FAIL'}")
        for failure in result.failures:
            print(f"    {failure}")


if __name__ == "__main__":
    main()
