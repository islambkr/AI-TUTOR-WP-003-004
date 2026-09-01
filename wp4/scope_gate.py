"""scope_gate.py -- Step 2 of WP-004: the deterministic scope gate.

The gate decides what one item is allowed to draw on. It contains no model call
and no heuristic: an entity, a relation or a fact is either on the item's
allowlist and asserted in the ontology, or it is refused. This is the point of
the work package -- a prompt saying "stay inside the ontology" is a request,
whereas this is a decision the generator cannot reach.

Graph access is reused from the WP-003 service rather than reimplemented, so
there remains exactly one piece of code that reads the ontology.

Run it:
    python -m wp4.scope_gate                 summarise every item's scope
    python -m wp4.scope_gate ITEM-001        print one scope in full
"""

import sys
from pathlib import Path

import rdflib
import yaml
from pydantic import BaseModel

from .schemas import EvidenceTriple, Item, OntologyScope

# The deterministic graph service from WP-003. The work package asks that its
# ontology path become an input; until that refactor lands, importing the module
# keeps a single reader of the ontology, which is the property that matters.
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "deliverable" / "qa_agent")
)

import graph_service  # noqa: E402

ITEM_FILE = Path(__file__).parent / "items" / "comp101_L10_ontology_gated_items.yaml"


def to_owl_property(relation_id: str) -> str:
    """Translate an item file relation id into the OWL property name.

    The item file writes relations in snake_case (`depends_on`, `produces_type`)
    while the ontology declares them in camelCase (`dependsOn`, `producesType`).
    Every one of the fourteen relation ids used across the 51 items differs this
    way, so without this translation the gate would refuse *all* real evidence
    while looking like it was working -- an empty allowlist rejects quietly.

    Whether the item file should instead be corrected at source is an open
    question for the mentor review; this function is the reversible answer.
    """
    head, *rest = relation_id.split("_")
    return head + "".join(word.capitalize() for word in rest)


def load_items(path: Path = ITEM_FILE) -> dict[str, Item]:
    """Read the mentor-approved item file, keyed by item id."""
    document = yaml.safe_load(path.read_text())
    return {record["id"]: Item(**record) for record in document["items"]}


def _entity_iri(course_id: str):
    """The IRI of the individual carrying this courseId, or None."""
    for subject in graph_service.GRAPH.subjects(
        graph_service.OOP.courseId, rdflib.Literal(course_id)
    ):
        return subject
    return None


def _course_id(iri) -> str:
    return graph_service._course_id_of(iri)


def collect_evidence(
    allowed_entities: set[str], allowed_relations: set[str]
) -> list[EvidenceTriple]:
    """Every asserted fact both of whose ends the gate permits.

    A fact qualifies only when its predicate is allowed *and* its subject is
    allowed *and* its object is allowed. Datatype facts such as `definition`
    have a literal object, which the gate treats as carried by the subject and
    so allowed with it; object properties must have both ends on the allowlist,
    which is what stops the evidence set from reaching outside the item.
    """
    evidence: list[EvidenceTriple] = []

    for course_id in sorted(allowed_entities):
        subject = _entity_iri(course_id)
        if subject is None:
            continue

        for predicate, obj in graph_service.GRAPH.predicate_objects(subject):
            name = graph_service._local_name(predicate)
            if name not in allowed_relations:
                continue

            if predicate in graph_service.DATATYPE_PROPERTIES:
                evidence.append(
                    EvidenceTriple(subject=course_id, predicate=name, object=str(obj))
                )
                continue

            other = _course_id(obj)
            if other and other in allowed_entities:
                evidence.append(
                    EvidenceTriple(subject=course_id, predicate=name, object=other)
                )

    return evidence


def build_scope(item: Item, max_depth: int | None = None) -> OntologyScope:
    """Resolve one item's allowlist into a scope with its supporting evidence.

    max_depth is carried through from the item rather than used to traverse: the
    item file ships an explicit allowlist, so the depth is a description of how
    that list was drawn rather than an instruction to this function. Overriding
    it here does not widen the scope, and is not meant to.
    """
    gate = item.ontology_gate
    allowed_entities = set(gate.allowed_entity_ids) | set(gate.anchor_ids)
    allowed_relations = {to_owl_property(r) for r in gate.allowed_relation_ids}

    return OntologyScope(
        item_id=item.id,
        anchors=gate.anchor_ids,
        max_depth=gate.max_depth if max_depth is None else max_depth,
        allowed_entities=allowed_entities,
        allowed_relations=allowed_relations,
        evidence=collect_evidence(allowed_entities, allowed_relations),
    )


def is_entity_allowed(scope: OntologyScope, entity_id: str) -> bool:
    return entity_id in scope.allowed_entities


def is_relation_allowed(scope: OntologyScope, relation: str) -> bool:
    """Accept either spelling, so a caller reading the item file is not punished."""
    return (
        relation in scope.allowed_relations
        or to_owl_property(relation) in scope.allowed_relations
    )


def is_evidence_allowed(scope: OntologyScope, triple: EvidenceTriple) -> bool:
    """True only for a fact the gate actually collected.

    Membership rather than recomputation: a triple whose parts are each allowed
    but which the ontology never asserts is exactly the fabricated citation this
    check exists to catch.
    """
    return any(
        triple.subject == known.subject
        and to_owl_property(triple.predicate) == known.predicate
        and triple.object == known.object
        for known in scope.evidence
    )


class DirectionMismatch(BaseModel):
    """A triple the item file declares in the direction the gate did not collect.

    `collected` holds the same edge as the gate has it, read the other way. That
    it is never None for any of the ten mismatches in the current file is the
    whole point: no evidence is missing, only the spelling of the direction
    differs, and a reader who sees the pair together can tell those two
    situations apart.
    """

    declared: EvidenceTriple
    collected: EvidenceTriple | None = None

    def __str__(self) -> str:
        if self.collected is None:
            return f"{self.declared}  (not collected in either direction)"
        return f"{self.declared}  collected as  {self.collected}"


def compare_declared_evidence(
    item: Item, scope: OntologyScope | None = None
) -> list[DirectionMismatch]:
    """Triples the item file declares that the gate does not collect as written.

    The item file carries its own `evidence_triples` alongside the allowlist.
    The gate does not trust that field -- it resolves evidence from the ontology
    -- so the two can disagree, and where they do it is worth knowing.

    Every disagreement in the current file has one cause: the declared triple
    uses one direction of an inverse pair while the allowlist names the other,
    so the file permits `has_example` and then cites `example_of`. The fact
    itself is present; each mismatch therefore carries the collected inverse,
    because "the gate refuses this evidence" and "the gate has this evidence the
    other way round" are very different reports.

    Whether an allowed relation should imply its inverse is a policy question
    for the mentor, not one this function decides.

    Pass `scope` when the caller already has it; otherwise it is rebuilt.
    """
    scope = build_scope(item) if scope is None else scope
    collected = {(t.subject, t.predicate, t.object): t for t in scope.evidence}

    mismatches = []
    for subject, relation, obj in item.ontology_gate.evidence_triples:
        declared = EvidenceTriple(
            subject=subject, predicate=to_owl_property(relation), object=obj
        )
        if (declared.subject, declared.predicate, declared.object) in collected:
            continue

        inverse = graph_service.INVERSE_OF.get(graph_service.OOP[declared.predicate])
        key = (
            (declared.object, graph_service._local_name(inverse), declared.subject)
            if inverse is not None
            else None
        )
        mismatches.append(
            DirectionMismatch(declared=declared, collected=collected.get(key))
        )

    return mismatches


def main() -> None:
    items = load_items()

    if len(sys.argv) > 1:
        wanted = sys.argv[1]
        matches = [i for key, i in items.items() if wanted in key]
        if not matches:
            sys.exit(f"no item matching {wanted!r}")
        for item in matches:
            scope = build_scope(item)
            print(f"\n{item}")
            print(f"  {scope}")
            for triple in scope.evidence:
                print(f"    {triple}")
            for mismatch in compare_declared_evidence(item, scope):
                print(f"  declared in the other direction: {mismatch}")
        return

    print(f"{len(items)} items\n")
    empty, flipped = [], []
    for item in items.values():
        scope = build_scope(item)
        if not scope.evidence:
            empty.append(item.id)
        if compare_declared_evidence(item, scope):
            flipped.append(item.id)
        print(f"{len(scope.evidence):>3} triples  {item}")

    if empty:
        print(f"\n{len(empty)} items resolved no evidence: {', '.join(empty)}")
    if flipped:
        print(
            f"\n{len(flipped)} items declare a triple in the direction opposite "
            f"to their allowlist; the gate holds every one of those facts the "
            f"other way round: {', '.join(flipped)}"
        )


if __name__ == "__main__":
    main()
