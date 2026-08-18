"""reasoning_delta.py -- how many facts a reasoner adds to comp101_L10.owl.

Produces the figures quoted in report.md section 2, so a reviewer can rerun
them rather than take them on trust.

Run it:  .venv/bin/python reasoning_delta.py
"""

from collections import Counter
from pathlib import Path

import owlrl
import rdflib
from rdflib.namespace import OWL, RDF

ONTOLOGY_PATH = Path(__file__).with_name("comp101_L10.owl")
OOP = rdflib.Namespace("http://comp101.sase.um6p.ma/ontology/oop#")


def local(term) -> str:
    return str(term).split("#")[-1]


asserted_graph = rdflib.Graph().parse(ONTOLOGY_PATH, format="xml")
asserted = set(asserted_graph)

reasoned = rdflib.Graph().parse(ONTOLOGY_PATH, format="xml")
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(reasoned)

# Keep only statements about named entities of this ontology; OWL-RL also emits
# a large amount of vocabulary bookkeeping that says nothing about the lecture.
new = [
    (s, p, o)
    for s, p, o in set(reasoned) - asserted
    if str(s).startswith(str(OOP))
    and str(o).startswith(str(OOP))
    and not isinstance(s, rdflib.BNode)
    and not isinstance(o, rdflib.BNode)
    and s != o
]

print(f"asserted triples        : {len(asserted)}")
print(f"after OWL-RL closure    : {len(reasoned)}")
print(f"new statements about oop entities: {len(new)}\n")

for predicate, count in Counter(local(p) for _, p, _ in new).most_common():
    print(f"  {count:>3}  {predicate}")

types = [(s, o) for s, p, o in new if p == RDF.type]
print(f"\ninferred rdf:type: {len(types)} statements across {len({s for s, _ in types})} individuals")

print("\ntransitive properties, and whether they close any chains:")
for prop in sorted(asserted_graph.subjects(RDF.type, OWL.TransitiveProperty), key=str):
    added = sum(1 for _, p, _ in new if p == prop)
    print(f"  {local(prop):<12} {len(list(asserted_graph.subject_objects(prop))):>3} asserted, {added:>2} inferred")
