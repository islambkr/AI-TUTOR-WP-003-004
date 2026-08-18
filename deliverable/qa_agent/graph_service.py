"""graph_service.py -- Step 4 of AI-TUTOR-WP-003: the deterministic graph service.

This module is the only place that talks to the ontology. It answers questions
about comp101_L10.owl with plain Python dictionaries and lists, so that every
fact returned can be traced back to a triple in the RDF graph.

Rules from the work package (section 5.4):
  * No LLM is used in this file. Same input -> same output, every time.
  * Results are structured data, never prose.
  * Each record carries the IRI, the identifier, and the label.

Return contract:
  * Every record is a dict with a "status" key.
  * "ok" means a real result.
"""

from collections import deque
from pathlib import Path

from rdflib import BNode, Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ONTOLOGY_PATH = Path(__file__).with_name("comp101_L10.owl")

# Parse once, at import time. Loading is the slow part (~978 triples), and the
# file is read-only input, so every function shares this one graph.
GRAPH = Graph() # declare an empty set of triples 
GRAPH.parse(ONTOLOGY_PATH, format="xml") # This fills the graph with triples from the ontology

# declaring the prefix for OOP namespace, so that we can use it to create URIs for the ontology terms
OOP = Namespace("http://comp101.sase.um6p.ma/ontology/oop#")


def _local_name(iri) -> str:
    """Return the readable tail of an IRI: '...oop#Method' -> 'Method'."""
    return str(iri).split("#")[-1]


def _label_of(iri) -> str:
    """Return the rdfs:label of an entity, or "" when it has none.

    GRAPH.value() returns None if the triple is absent, so the result is
    converted with str() only after that check -- str(None) would give "None".
    """
    label = GRAPH.value(iri, RDFS.label)
    return str(label) if label is not None else ""


def _comment_of(iri) -> str:
    """Return the rdfs:comment of an entity, or "" when it has none."""
    comment = GRAPH.value(iri, RDFS.comment)
    return str(comment) if comment is not None else ""


def _course_id_of(iri) -> str:
    """Return the oop:courseId of an entity, or "" when it has none.

    Only individuals carry a courseId; classes and properties do not.
    """
    course_id = GRAPH.value(iri, OOP.courseId)
    return str(course_id) if course_id is not None else ""


def _citation_of(iri) -> str:
    """How an answer should name this entity: "Label (IDENTIFIER)".

    The work package requires an identifier in every factual answer. Building
    the string here rather than leaving the model to assemble it is what makes
    that reliable.
    """
    identifier = _course_id_of(iri) or _local_name(iri) #classes dont have no courseID so instead we use their local names
    return f"{_label_of(iri) or identifier} ({identifier})"


def _not_found(query: str, message: str) -> dict:
    """Build the record returned when the input matches nothing."""
    return {"status": "not_found", "query": query, "message": message}


def _find_class(type_label: str):
    """Resolve free text to one class IRI, or None when nothing matches.

    Matching is case-insensitive and accepts either the class name
    ("MethodRole") or its rdfs:label, so "methodrole" and "MethodRole" both
    work. This covers the work package's "a label differs only by case" case.
    """
    wanted = type_label.strip().casefold()
    if not wanted:
        return None

    named = [
        class_iri
        for class_iri in GRAPH.subjects(RDF.type, OWL.Class)
        if not isinstance(class_iri, BNode)
    ]

    def names_of(class_iri):
        return (_local_name(class_iri).casefold(), _label_of(class_iri).casefold())

    # Tier 1: exact match on the class name or its label.
    for class_iri in sorted(named, key=str):
        if wanted in names_of(class_iri):
            return class_iri

    # Tier 2: the same word in the singular, so "methods" finds Method.
    singular = wanted[:-1] if wanted.endswith("s") else wanted
    for class_iri in sorted(named, key=str):
        if singular in names_of(class_iri):
            return class_iri

    # Tier 3: a class whose name contains the word, so "error" and "errors"
    # both find ErrorType. Only accepted when exactly one class matches, so an
    # ambiguous word never resolves silently to the wrong class.
    contains = [
        class_iri
        for class_iri in sorted(named, key=str)
        if any(singular in name for name in names_of(class_iri))
    ]
    if len(contains) == 1:
        return contains[0]

    return None


def list_classes() -> list[dict]:
    """List every named class declared in the ontology.

    Anonymous classes are skipped: the ontology defines TypeProducer and
    ImplementorType with owl:unionOf, which creates blank-node class
    expressions. Those are real owl:Class nodes but have no IRI and no label,
    so they are not useful to a student or to the agent.

    Returns 16 records, sorted by name so the output is reproducible.
    """
    records = []

    for class_iri in GRAPH.subjects(RDF.type, OWL.Class):
        if isinstance(class_iri, BNode):
            continue

        records.append(
            {
                "status": "ok",
                "iri": str(class_iri),
                "id": _local_name(class_iri),
                "label": _label_of(class_iri),
                "comment": _comment_of(class_iri),
            }
        )

    return sorted(records, key=lambda record: record["id"])


# The ontology declares which properties link to other entities (object
# properties) and which hold plain values (datatype properties). Reading those
# declarations from the file means this module never hardcodes a property list.
OBJECT_PROPERTIES = set(GRAPH.subjects(RDF.type, OWL.ObjectProperty))
DATATYPE_PROPERTIES = set(GRAPH.subjects(RDF.type, OWL.DatatypeProperty))
SYMMETRIC_PROPERTIES = set(GRAPH.subjects(RDF.type, OWL.SymmetricProperty))

# owl:inverseOf pairs, read from the ontology and stored both ways round.
# The file asserts both halves of every pair (teaches AND taughtIn), so without
# this map every fact would be reported twice.
INVERSE_OF = {}
for _left, _right in GRAPH.subject_objects(OWL.inverseOf):
    INVERSE_OF[_left] = _right
    INVERSE_OF[_right] = _left


def _named_entities() -> list:
    """Every individual and every named class, i.e. everything findable by name.

    Classes are included because a student may reasonably ask "what is a
    Method?" meaning the class, not one of the five dunder methods.
    """
    individuals = set(GRAPH.subjects(RDF.type, OWL.NamedIndividual))
    classes = {
        class_iri
        for class_iri in GRAPH.subjects(RDF.type, OWL.Class)
        if not isinstance(class_iri, BNode)
    }
    return sorted(individuals | classes, key=str)


def _kind_of(iri) -> str:
    """Say whether an IRI is an individual or a class."""
    return "class" if (iri, RDF.type, OWL.Class) in GRAPH else "individual"


def _types_of(iri) -> list[str]:
    """The class names an individual belongs to, ignoring owl:NamedIndividual."""
    return sorted(
        _local_name(type_iri)
        for type_iri in GRAPH.objects(iri, RDF.type)
        if type_iri != OWL.NamedIndividual and type_iri != OWL.Class
    )


def _entity_record(iri, matched_by: str = "") -> dict:
    """The standard record for one entity, used by every function below."""
    identifier = _course_id_of(iri) or _local_name(iri)
    record = {
        "status": "ok",
        "iri": str(iri),
        "id": identifier,
        "label": _label_of(iri) or identifier,
        # Ready-made way to name this entity in an answer, so the model never
        # has to assemble "label (id)" itself and forget to.
        "citation": _citation_of(iri),
        "kind": _kind_of(iri),
        "types": _types_of(iri),
    }
    if matched_by:
        record["matched_by"] = matched_by
    return record


def find_entity(label_or_id: str) -> list[dict]:
    """Find the entities matching a label, a course id, a local name, or an IRI.

    Matching happens in two tiers, and the order matters:

      1. EXACT (case-insensitive) against courseId, rdfs:label, the local name
         or the full IRI. In this ontology no two entities share a label or a
         courseId, so an exact hit is always a single entity.
      2. PARTIAL, only when tier 1 found nothing: any entity whose label
         contains the text. This is what produces several matches, e.g.
         "method" appears in 10 labels.

    Exact-first is what keeps common questions unambiguous. The label "Class"
    belongs to one individual (COOP001) but is a substring of 10 others, so a
    student asking about "Class" must get that one entity, not a list of ten.

    Returns a one-element list holding a "not_found" record when nothing
    matches at all.
    """
    wanted = label_or_id.strip().casefold()

    if not wanted:
        return [_not_found(label_or_id, "Empty query. Give a label, a courseId, or an IRI.")]

    exact = []
    partial = []

    for iri in _named_entities():
        course_id = _course_id_of(iri)
        label = _label_of(iri)
        name = _local_name(iri)

        if wanted == course_id.casefold():
            exact.append((iri, "courseId"))
        elif wanted == label.casefold():
            # Flag a case-only difference so the agent can say which entity it assumed.
            matched_by = "label" if label == label_or_id.strip() else "label (different case)"
            exact.append((iri, matched_by))
        elif wanted == name.casefold():
            exact.append((iri, "name"))
        elif wanted == str(iri).casefold():
            exact.append((iri, "iri"))
        elif wanted in label.casefold():
            partial.append((iri, "partial label"))

    matches = exact or partial

    if not matches:
        return [
            _not_found(
                label_or_id,
                f"Nothing in the ontology matches '{label_or_id}'.",
            )
        ]

    records = [_entity_record(iri, matched_by) for iri, matched_by in matches]
    return sorted(records, key=lambda record: record["label"])


def _ambiguous(query: str, records: list[dict]) -> dict:
    """Build the record returned when the input matches several entities.

    The candidates travel with the record under "matches" so the agent can list
    them and ask the student which one they meant, instead of guessing.
    """
    return {
        "status": "ambiguous",
        "query": query,
        "message": f"'{query}' matches {len(records)} entities. Ask which one is meant.",
        "matches": records,
    }


def _resolve(label_or_id: str):
    """Resolve free text to exactly one entity.

    Returns a pair (iri, problem):
      * (URIRef, None)  the text named exactly one entity
      * (None, record)  it named none, or several -- the record explains which

    Every single-entity function starts with this, so "not found" and
    "ambiguous" are handled identically everywhere.
    """
    matches = find_entity(label_or_id)

    if matches[0]["status"] == "not_found":
        return None, matches[0]

    if len(matches) > 1:
        return None, _ambiguous(label_or_id, matches)

    return URIRef(matches[0]["iri"]), None


def _attributes_of(iri) -> dict:
    """Every datatype-property value on an entity, as plain strings.

    These are the literal facts -- definition, cognitive_type, best_practice --
    as opposed to links to other entities.
    """
    attributes = {}

    for predicate, value in GRAPH.predicate_objects(iri):
        if predicate in DATATYPE_PROPERTIES:
            attributes[_local_name(predicate)] = str(value)

    comment = _comment_of(iri)
    if comment:
        attributes["comment"] = comment

    return attributes


def _relations_of(iri) -> list[dict]:
    """Every object-property link touching an entity, in both directions.

    Symmetric properties (oop:contrastsWith) are reported once, as "symmetric",
    because the ontology asserts them in both directions and listing them twice
    would suggest two separate facts.
    """
    seen = set()
    relations = []

    for predicate, other in GRAPH.predicate_objects(iri):
        if predicate not in OBJECT_PROPERTIES:
            continue
        direction = "symmetric" if predicate in SYMMETRIC_PROPERTIES else "outgoing"
        key = (predicate, other, direction)
        if key in seen:
            continue
        seen.add(key)
        relations.append(
            {
                "status": "ok",
                "predicate": _local_name(predicate),
                "direction": direction,
                "statement": f"{_citation_of(iri)} {_local_name(predicate)} {_citation_of(other)}",
                "iri": str(other),
                "id": _course_id_of(other) or _local_name(other),
                "label": _label_of(other),
                "citation": _citation_of(other),
            }
        )

    for other, predicate in GRAPH.subject_predicates(iri):
        if predicate not in OBJECT_PROPERTIES:
            continue
        if predicate in SYMMETRIC_PROPERTIES and (iri, predicate, other) in GRAPH:
            continue  # the same symmetric fact was already reported outgoing
        # Skip an incoming relation whose inverse was already reported going
        # out. "str isProducedBy __repr__" is the same fact as
        # "__repr__ producesType str", and the agent should hear it once.
        if (INVERSE_OF.get(predicate), other, "outgoing") in seen:
            continue
        key = (predicate, other, "incoming")
        if key in seen:
            continue
        seen.add(key)
        relations.append(
            {
                "status": "ok",
                "predicate": _local_name(predicate),
                "direction": "incoming",
                "statement": f"{_citation_of(other)} {_local_name(predicate)} {_citation_of(iri)}",
                "iri": str(other),
                "id": _course_id_of(other) or _local_name(other),
                "label": _label_of(other),
                "citation": _citation_of(other),
            }
        )

    return sorted(relations, key=lambda r: (r["predicate"], r["label"]))


def describe_entity(label_or_id: str) -> dict:
    """Return everything the ontology asserts about one entity.

    The record holds the identity (iri, id, label, kind, types), the literal
    attributes (definition and friends), and every relation in both directions.

    Returns a "not_found" or "ambiguous" record instead when the text does not
    name exactly one entity.
    """
    iri, problem = _resolve(label_or_id)

    if problem is not None:
        return problem

    record = _entity_record(iri)
    record["attributes"] = _attributes_of(iri)
    record["relations"] = _relations_of(iri)
    return record


def get_relations(label_or_id: str) -> list[dict]:
    """List every object-property relation of an entity, in both directions.

    Each record names the relation and the entity at the other end, and says
    which way the arrow points:
      * "outgoing"  the entity is the subject   (Encapsulation hasPart Getter)
      * "incoming"  the entity is the object    (Data Hiding dependsOn Encapsulation)
      * "symmetric" the relation has no direction (contrastsWith)

    Incoming relations are the ones invisible when reading the RDF/XML file,
    because they are asserted elsewhere in the document.

    Returns an empty list when the entity exists but has no relations, and a
    one-element list holding the problem record when the text names no entity
    or several.
    """
    iri, problem = _resolve(label_or_id)

    if problem is not None:
        return [problem]

    return _relations_of(iri)


def relation_names() -> list[str]:
    """Every object-property name in the ontology, sorted.

    Used to validate a requested relation and to tell the caller what is
    available when they ask for one that does not exist.
    """
    return sorted(_local_name(prop) for prop in OBJECT_PROPERTIES)


def get_relations_by_name(label_or_id: str, relation: str) -> list[dict]:
    """Return the facts in which the entity is the SUBJECT of a named property.

    get_relations_by_name(X, "hasPart") answers "X hasPart what?" and never
    "what hasPart X?" -- those are different questions, and the second one is
    asked with "partOf" instead. Direction is part of the question.

    Both spellings of an inverse pair are consulted, but only in the position
    that preserves the question: "X hasPart ?y" is also satisfied by an asserted
    "?y partOf X", because owl:inverseOf makes those the same fact. What is NOT
    accepted is "X partOf ?y", which is the opposite claim.

    Returns an empty list when the entity has that relation nowhere, and a
    one-element list holding a problem record when the entity or the relation
    name is unknown.
    """
    iri, problem = _resolve(label_or_id)

    if problem is not None:
        return [problem]

    wanted = relation.strip().casefold()
    property_iri = next(
        (prop for prop in sorted(OBJECT_PROPERTIES, key=str)
         if _local_name(prop).casefold() == wanted),
        None,
    )

    if property_iri is None:
        return [
            _not_found(
                relation,
                f"No relation named '{relation}'. Available: {', '.join(relation_names())}.",
            )
        ]

    # "X <relation> ?other" asserted directly...
    others = set(GRAPH.objects(iri, property_iri))

    # ...or the same fact asserted from the other end as "?other <inverse> X".
    inverse = INVERSE_OF.get(property_iri)
    if inverse is not None:
        others |= set(GRAPH.subjects(inverse, iri))

    name = _local_name(property_iri)
    records = []

    for other in sorted(others, key=str):
        records.append(
            {
                "status": "ok",
                "predicate": name,
                "direction": "symmetric" if property_iri in SYMMETRIC_PROPERTIES else "outgoing",
                "statement": f"{_citation_of(iri)} {name} {_citation_of(other)}",
                "iri": str(other),
                "id": _course_id_of(other) or _local_name(other),
                "label": _label_of(other),
                "citation": _citation_of(other),
            }
        )

    return sorted(records, key=lambda record: record["label"])


def get_dependencies(
    label_or_id: str,
    transitive: bool = False,
    direction: str = "depends_on",
) -> list[dict]:
    """Return what an entity depends on -- or what depends on it.

    direction:
      * "depends_on"  the prerequisites of the entity   (default)
      * "required_by" the entities that need this one

    transitive:
      * False  one hop only, via oop:dependsOn
      * True   any number of hops, via the SPARQL property path oop:dependsOn+

    oop:dependsOn is declared owl:TransitiveProperty, but SPARQL does not read
    that declaration -- the "+" in the property path is what walks the chain.
    Without it, "Data Hiding" reports 2 prerequisites; with it, 3, because
    Data Hiding -> Encapsulation -> Class.

    Each record carries "direct": True for a one-hop prerequisite, False for one
    reached only through a chain, so the agent can phrase the two differently.

    Returns an empty list when the entity has no dependencies, and a
    one-element list holding the problem record when resolution fails.
    """
    if direction not in ("depends_on", "required_by"):
        return [
            _not_found(
                direction,
                "direction must be 'depends_on' or 'required_by'.",
            )
        ]

    iri, problem = _resolve(label_or_id)

    if problem is not None:
        return [problem]

    # The property path is written once and pointed either way round: for
    # "required_by" the start entity sits in the object position instead.
    path = "oop:dependsOn+" if transitive else "oop:dependsOn"
    pattern = (
        f"?start {path} ?other ."
        if direction == "depends_on"
        else f"?other {path} ?start ."
    )
    rows = GRAPH.query(
        f"SELECT DISTINCT ?other WHERE {{ {pattern} }}",
        initNs={"oop": OOP},
        initBindings={"start": iri},
    )

    # One hop is what "direct" means, so compute that set once to label each row.
    if direction == "depends_on":
        direct_neighbours = set(GRAPH.objects(iri, OOP.dependsOn))
    else:
        direct_neighbours = set(GRAPH.subjects(OOP.dependsOn, iri))

    records = []

    start_cited = _citation_of(iri)

    for row in rows:
        other = row.other
        if other == iri:
            continue  # a cycle can walk back to the start; never report it
        record = _entity_record(other)
        record["relation"] = "dependsOn" if direction == "depends_on" else "isRequiredBy"
        record["direct"] = other in direct_neighbours
        # Spell the fact out in subject-predicate-object order. For
        # "required_by" the other entity is the subject, and a model that
        # rebuilds the sentence itself states it backwards.
        other_cited = record["citation"]
        record["statement"] = (
            f"{start_cited} dependsOn {other_cited}"
            if direction == "depends_on"
            else f"{other_cited} dependsOn {start_cited}"
        )
        records.append(record)

    return sorted(records, key=lambda record: (not record["direct"], record["label"]))


# oop:teaches links the lecture to all 65 other individuals, so every pair of
# entities is two hops apart through it. That path is true but says nothing
# ("both are taught in Lecture 10"), so the search ignores these two predicates
# and reports conceptual routes instead.
PATH_EXCLUDED_PREDICATES = {OOP.teaches, OOP.taughtIn}


def _neighbours(iri) -> list[tuple]:
    """Every entity one hop away, as (predicate, other, direction) triples.

    Both directions are followed. The ontology asserts both halves of each
    inverse pair, so outgoing edges alone would usually be enough -- but
    following incoming edges too means the search still works if a future
    ontology omits an inverse.
    """
    steps = []

    for predicate, other in GRAPH.predicate_objects(iri):
        if predicate in OBJECT_PROPERTIES and predicate not in PATH_EXCLUDED_PREDICATES:
            steps.append((predicate, other, "outgoing"))

    for other, predicate in GRAPH.subject_predicates(iri):
        if predicate in OBJECT_PROPERTIES and predicate not in PATH_EXCLUDED_PREDICATES:
            steps.append((predicate, other, "incoming"))

    # Sorted so the search explores in a fixed order and the chosen path is
    # identical on every run -- the work package requires deterministic results.
    return sorted(steps, key=lambda step: (str(step[1]), str(step[0])))


def _rebuild_path(came_from: dict, source, target) -> list[dict]:
    """Turn the breadth-first search's parent map into an ordered step list.

    came_from maps each visited entity to (previous_entity, predicate,
    direction). Walking it from the target back to the source gives the path
    reversed, so the result is flipped before returning.
    """
    steps = []
    current = target

    while current != source:
        previous, predicate, direction = came_from[current]
        here = _label_of(previous) or _local_name(previous)
        there = _label_of(current) or _local_name(current)
        here_cited = _citation_of(previous)
        there_cited = _citation_of(current)
        predicate_name = _local_name(predicate)
        # Spell the fact out in subject-predicate-object order. An "incoming"
        # step is asserted the other way round, and a model reading the raw
        # fields left to right will otherwise state it backwards.
        statement = (
            f"{here_cited} {predicate_name} {there_cited}"
            if direction == "outgoing"
            else f"{there_cited} {predicate_name} {here_cited}"
        )
        steps.append(
            {
                "from": here,
                "predicate": predicate_name,
                "direction": direction,
                "to": there,
                "statement": statement,
                "to_id": _course_id_of(current) or _local_name(current),
                "to_citation": _citation_of(current),
                "to_iri": str(current),
            }
        )
        current = previous

    steps.reverse()
    return steps


def find_path(source: str, target: str, max_depth: int = 5) -> dict:
    """Find one shortest chain of relations from `source` to `target`.

    Breadth-first search, so the first route found is a shortest one. A single
    SPARQL query cannot do this: property paths test whether some path exists
    for one named predicate, but cannot mix predicates or report the steps.

    Returns status "no_path" when both entities exist but no chain of at most
    max_depth relations connects them, and "not_found" / "ambiguous" when
    either end fails to resolve.
    """
    source_iri, problem = _resolve(source)
    if problem is not None:
        return problem

    target_iri, problem = _resolve(target)
    if problem is not None:
        return problem

    source_record = _entity_record(source_iri)
    target_record = _entity_record(target_iri)

    if source_iri == target_iri:
        return {
            "status": "ok",
            "source": source_record,
            "target": target_record,
            "length": 0,
            "steps": [],
        }

    # Standard breadth-first search: a queue of (entity, depth), a visited set
    # so nothing is expanded twice, and came_from to reconstruct the route.
    queue = deque([(source_iri, 0)])
    visited = {source_iri}
    came_from = {}

    while queue:
        current, depth = queue.popleft()

        if depth >= max_depth:
            continue  # too deep to extend, but other branches may still be short

        for predicate, other, direction in _neighbours(current):
            if other in visited:
                continue

            visited.add(other)
            came_from[other] = (current, predicate, direction)

            if other == target_iri:
                steps = _rebuild_path(came_from, source_iri, target_iri)
                return {
                    "status": "ok",
                    "source": source_record,
                    "target": target_record,
                    "length": len(steps),
                    "steps": steps,
                }

            queue.append((other, depth + 1))

    return {
        "status": "no_path",
        "source": source_record,
        "target": target_record,
        "message": (
            f"No chain of at most {max_depth} relations connects "
            f"'{source_record['label']}' to '{target_record['label']}'."
        ),
    }


def list_entities_by_type(type_label: str) -> list[dict]:
    """List the individuals of one class, e.g. list_entities_by_type("Concept").

    Three outcomes, all of them normal:
      * the class exists and has individuals -> a list of records
      * the class exists but has none        -> an EMPTY list
      * the class does not exist             -> a ONE-element list holding a
                                                "not_found" record

    The empty list and the not_found list mean different things, and the agent
    must be able to tell them apart: "Algorithm has no entities recorded" is a
    true answer, while "there is no class called Algorythm" is a correction.
    """
    class_iri = _find_class(type_label)

    if class_iri is None:
        return [
            _not_found(
                type_label,
                f"No class named '{type_label}'. Use list_classes() to see the 16 available classes.",
            )
        ]

    records = []

    for entity_iri in GRAPH.subjects(RDF.type, class_iri):
        records.append(
            {
                "status": "ok",
                "iri": str(entity_iri),
                "id": _course_id_of(entity_iri) or _local_name(entity_iri),
                "label": _label_of(entity_iri),
                "type": _local_name(class_iri),
            }
        )

    return sorted(records, key=lambda record: record["id"])


if __name__ == "__main__":
    print("--- list_classes() ---")
    for record in list_classes():
        print(f"{record['id']:<20} {record['label']}")
    print(f"({len(list_classes())} classes)\n")

    print("--- list_entities_by_type('Method') ---")
    for record in list_entities_by_type("Method"):
        print(f"{record['id']:<12} {record['label']}")

    print("\n--- case-insensitive: list_entities_by_type('datatype') ---")
    for record in list_entities_by_type("datatype"):
        print(f"{record['id']:<12} {record['label']}")

    print("\n--- class exists but is empty: list_entities_by_type('Algorithm') ---")
    print(list_entities_by_type("Algorithm"))

    print("\n--- class does not exist: list_entities_by_type('Algorythm') ---")
    print(list_entities_by_type("Algorythm"))

    print("\n--- find_entity, four ways to name the same thing ---")
    for probe in ["__repr__", "MOOP003", "mooP003", "http://comp101.sase.um6p.ma/ontology/oop#MOOP003"]:
        hits = find_entity(probe)
        print(f"  {probe[:44]:<46} -> {hits[0]['label']:<12} via {hits[0].get('matched_by')}")

    print("\n--- exact beats partial: find_entity('Class') ---")
    for record in find_entity("Class"):
        print(f"  {record['id']:<12} {record['label']:<20} {record['kind']}")

    print("\n--- 'method' is an exact class name, so tier 1 wins ---")
    for record in find_entity("method"):
        print(f"  {record['id']:<12} {record['label']:<26} {record['kind']}")

    print("\n--- genuinely ambiguous (partial only): find_entity('abstract') ---")
    for record in find_entity("abstract"):
        print(f"  {record['id']:<12} {record['label']:<26} via {record['matched_by']}")

    print("\n--- nothing matches: find_entity('gradient descent') ---")
    print(find_entity("gradient descent"))

    print("\n--- describe_entity('Encapsulation') ---")
    described = describe_entity("Encapsulation")
    print(f"  {described['id']} / {described['label']} ({described['kind']}, {described['types']})")
    for key, value in described["attributes"].items():
        print(f"    {key:<16} {value[:78]}")
    print(f"    relations       {len(described['relations'])}")
    for relation in described["relations"][:6]:
        print(f"      {relation['direction']:<10} {relation['predicate']:<14} {relation['label']}")

    print("\n--- describe_entity('abstract') -> ambiguous ---")
    problem = describe_entity("abstract")
    print(f"  status={problem['status']}  {problem['message']}")
    for candidate in problem["matches"]:
        print(f"      {candidate['id']:<18} {candidate['label']}")

    print("\n--- describe_entity('gradient descent') -> not_found ---")
    print(" ", describe_entity("gradient descent"))

    print("\n--- get_relations('__repr__') ---")
    for relation in get_relations("__repr__"):
        print(f"  {relation['direction']:<10} {relation['predicate']:<14} {relation['id']:<12} {relation['label']}")

    print("\n--- get_dependencies('Data Hiding')  direct only ---")
    for record in get_dependencies("Data Hiding"):
        print(f"  {record['id']:<12} {record['label']:<18} direct={record['direct']}")

    print("\n--- get_dependencies('Data Hiding', transitive=True) ---")
    for record in get_dependencies("Data Hiding", transitive=True):
        print(f"  {record['id']:<12} {record['label']:<18} direct={record['direct']}")

    print("\n--- get_dependencies('Class', direction='required_by') ---")
    for record in get_dependencies("Class", direction="required_by"):
        print(f"  {record['id']:<12} {record['label']:<26} direct={record['direct']}")

    print("\n--- no dependencies recorded: get_dependencies('__repr__') ---")
    print(" ", get_dependencies("__repr__"))

    print("\n--- find_path('Class', 'Data Hiding') ---")
    path = find_path("Class", "Data Hiding")
    print(f"  status={path['status']}  length={path['length']}")
    for step in path["steps"]:
        arrow = "->" if step["direction"] == "outgoing" else "<-"
        print(f"    {step['from']:<22} {arrow} {step['predicate']:<14} {step['to']}")

    print("\n--- find_path('__repr__', 'Metaclass', max_depth=1) -> too far ---")
    print(" ", find_path("__repr__", "Metaclass", max_depth=1)["status"])

    print("\n--- find_path('Class', 'gradient descent') -> not_found ---")
    print(" ", find_path("Class", "gradient descent")["status"])