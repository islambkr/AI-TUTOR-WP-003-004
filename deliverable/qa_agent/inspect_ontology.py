"""inspect_ontology.py -- Step 2 of AI-TUTOR-WP-003: inspect the ontology with RDFLib.

Prints a stable inventory of comp101_L10.owl: counts, and for every entity both
its local identifier and its human-readable label. Everything is sorted, so two
runs produce identical output.

Run it:  .venv/bin/python inspect_ontology.py
"""

from pathlib import Path

from rdflib import BNode, Graph, Namespace
from rdflib.namespace import OWL, RDF, RDFS

ONTOLOGY_PATH = Path(__file__).with_name("comp101_L10.owl")
OOP = Namespace("http://comp101.sase.um6p.ma/ontology/oop#")

graph = Graph()
graph.parse(ONTOLOGY_PATH, format="xml")


def local_name(iri) -> str:
    return str(iri).split("#")[-1]


def label_of(iri) -> str:
    label = graph.value(iri, RDFS.label)
    return str(label) if label is not None else "(no label)"


def course_id_of(iri) -> str:
    course_id = graph.value(iri, OOP.courseId)
    return str(course_id) if course_id is not None else ""


def named(subjects) -> list:
    """Drop blank nodes and sort, so the inventory is reproducible."""
    return sorted((s for s in subjects if not isinstance(s, BNode)), key=str)


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


# ---------------------------------------------------------------- ontology
ontology = next(graph.subjects(RDF.type, OWL.Ontology), None)
print(f"Ontology : {ontology}")
print(f"Version  : {graph.value(ontology, OWL.versionInfo)}")
print(f"Triples  : {len(graph)}")

# rdflib pre-binds around 30 well-known prefixes whether or not the file uses
# them, so only the ones a real term actually uses are worth reporting.
used_uris = {
    str(term)
    for triple in graph
    for term in triple
    if not isinstance(term, BNode) and str(term).startswith("http")
}
section("Namespace prefixes in use")
for prefix, uri in sorted(graph.namespaces()):
    if any(term.startswith(str(uri)) for term in used_uris):
        print(f"  {prefix or '(default)':<10} {uri}")

# ------------------------------------------------------------------ classes
classes = named(graph.subjects(RDF.type, OWL.Class))
anonymous = len(list(graph.subjects(RDF.type, OWL.Class))) - len(classes)
section(f"Named classes ({len(classes)}, plus {anonymous} anonymous class expressions)")
for class_iri in classes:
    count = len(list(graph.subjects(RDF.type, class_iri)))
    print(f"  {local_name(class_iri):<20} {label_of(class_iri):<24} {count:>2} individuals")

# --------------------------------------------------------------- properties
object_properties = named(graph.subjects(RDF.type, OWL.ObjectProperty))
section(f"Object properties ({len(object_properties)})")
for prop in object_properties:
    characteristics = sorted(
        local_name(t)
        for t in graph.objects(prop, RDF.type)
        if t != OWL.ObjectProperty
    )
    inverse = graph.value(prop, OWL.inverseOf)
    uses = len(list(graph.subject_objects(prop)))
    extra = ", ".join(characteristics)
    if inverse is not None:
        extra = f"{extra + ', ' if extra else ''}inverse of {local_name(inverse)}"
    print(f"  {local_name(prop):<18} {label_of(prop):<20} {uses:>3} uses   {extra}")

datatype_properties = named(graph.subjects(RDF.type, OWL.DatatypeProperty))
section(f"Datatype properties ({len(datatype_properties)})")
for prop in datatype_properties:
    domain = graph.value(prop, RDFS.domain)
    range_ = graph.value(prop, RDFS.range)
    uses = len(list(graph.subject_objects(prop)))
    print(
        f"  {local_name(prop):<18} {label_of(prop):<20} {uses:>3} uses   "
        f"domain {local_name(domain):<12} range {local_name(range_)}"
    )

# -------------------------------------------------------------- individuals
individuals = named(graph.subjects(RDF.type, OWL.NamedIndividual))
section(f"Named individuals ({len(individuals)})")
for individual in individuals:
    types = sorted(
        local_name(t)
        for t in graph.objects(individual, RDF.type)
        if t != OWL.NamedIndividual
    )
    print(
        f"  {course_id_of(individual) or local_name(individual):<16} "
        f"{label_of(individual):<32} {', '.join(types)}"
    )

# -------------------------------------------------------------- disjointness
section("Disjoint class declarations")
from rdflib.collection import Collection  # noqa: E402  (kept local to this section)

for axiom in graph.subjects(RDF.type, OWL.AllDisjointClasses):
    members = graph.value(axiom, OWL.members)
    names = sorted(local_name(m) for m in Collection(graph, members))
    print(f"  AllDisjointClasses over {len(names)} classes:")
    for name in names:
        print(f"    {name}")