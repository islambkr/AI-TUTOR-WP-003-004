"""Execute the SPARQL queries in queries.sparql against the ontology.

The acceptance criteria require that "at least 10 SPARQL queries return the
expected results". The queries were committed, but the evidence that they run
was a terminal transcript, so a query could break silently: a renamed property
or a typo in a prefix yields zero rows rather than an error.

Following the lesson recorded in report.md section 4.6, these tests do not
assert row counts copied from the queries' own output. Each expectation is
either a figure established independently (the inventory in the report), a
count taken straight from the triples with rdflib, or a structural invariant
that must hold whatever the data says.
"""

import re
import sys
from pathlib import Path

import pytest
import rdflib
from rdflib.namespace import OWL, RDF
from rdflib.plugins.sparql import prepareQuery

sys.path.insert(0, str(Path(__file__).parent.parent))

QUERY_FILE = Path(__file__).parent.parent / "queries.sparql"
ONTOLOGY = rdflib.Graph().parse(
    Path(__file__).parent.parent / "comp101_L10.owl", format="xml"
)
OOP = rdflib.Namespace("http://comp101.sase.um6p.ma/ontology/oop#")


def _load_queries() -> dict[int, str]:
    """Split queries.sparql into runnable queries, keyed by their number.

    The file declares its PREFIX block once at the top and then separates the
    queries with "# Query N:" banners, which keeps it readable in Protege's
    SPARQL tab. Each query therefore needs the shared prefixes prepended before
    it can run on its own.
    """
    text = QUERY_FILE.read_text()
    prefixes = "\n".join(re.findall(r"^PREFIX .*$", text, flags=re.MULTILINE))
    assert prefixes, "queries.sparql declares no PREFIX lines"

    # Everything from one "# Query N:" banner up to the next one.
    banner = re.compile(r"^# Query (\d+):", flags=re.MULTILINE)
    marks = [(int(m.group(1)), m.start()) for m in banner.finditer(text)]
    assert marks, "queries.sparql contains no '# Query N:' banners"

    queries = {}
    for position, (number, start) in enumerate(marks):
        end = marks[position + 1][1] if position + 1 < len(marks) else len(text)
        body = text[start:end]
        # Drop the banner's own comment lines; keep the query itself.
        body = "\n".join(
            line for line in body.splitlines() if not line.lstrip().startswith("#")
        )
        queries[number] = f"{prefixes}\n{body}"
    return queries


QUERIES = _load_queries()


def _rows(number: int) -> list:
    return list(ONTOLOGY.query(QUERIES[number]))


def test_file_declares_ten_queries():
    """The acceptance criteria ask for at least 10, numbered without gaps."""
    assert len(QUERIES) >= 10
    assert sorted(QUERIES) == list(range(1, len(QUERIES) + 1))


@pytest.mark.parametrize("number", sorted(QUERIES))
def test_every_query_is_valid_sparql(number):
    """A syntax error or an undeclared prefix fails here, not silently at run time."""
    prepareQuery(QUERIES[number])


@pytest.mark.parametrize("number", sorted(QUERIES))
def test_every_query_returns_rows(number):
    """The acceptance floor: a query that returns nothing has not been answered.

    SPARQL reports a pattern that matches nothing the same way it reports a
    misspelled property -- an empty result. So emptiness is the failure mode
    worth guarding, and no query in this file is meant to be empty.
    """
    assert _rows(number), f"query {number} returned no rows"


def test_query_1_finds_every_named_class():
    """16 named classes, the figure reported in README.md and report.md.

    The two anonymous union classes have no label and are not owl:Class
    subjects with an rdfs:label, so they are correctly absent.
    """
    classes = {row[0] for row in _rows(1)}
    assert len(classes) == 16


def test_queries_3_and_4_resolve_the_same_entity():
    """Lookup by rdfs:label and lookup by courseId must agree.

    Query 3 asks for the entity labelled "__repr__" and query 4 asks for the
    one whose courseId is "MOOP003". The ontology says these are one entity, so
    the two lookup paths the graph service depends on must return it.
    """
    by_label = {row[0] for row in _rows(3)}
    by_course_id = {row[0] for row in _rows(4)}

    assert by_label == by_course_id
    assert by_label == {OOP.MOOP003}


def test_query_7_contains_query_6():
    """Transitive dependencies must include the direct ones.

    Query 6 walks a single oop:dependsOn hop; query 7 walks one or more with a
    property path. Whatever the data holds, the closure cannot be missing a
    step it is built from -- so this holds without hardcoding either result.
    """
    direct = {row[0] for row in _rows(6)}
    transitive = {row[0] for row in _rows(7)}

    assert direct
    assert direct <= transitive


def test_query_8_matches_the_symmetric_property_in_both_directions():
    """oop:contrastsWith is symmetric, so the query must not depend on direction.

    The expected set is read from the triples with rdflib rather than from the
    query, so an asserted-direction change in the ontology cannot quietly make
    the query and its expectation agree on a subset.
    """
    subject = OOP.MR_OOP01
    expected = set(ONTOLOGY.objects(subject, OOP.contrastsWith)) | set(
        ONTOLOGY.subjects(OOP.contrastsWith, subject)
    )

    assert expected, "MR_OOP01 asserts no contrastsWith triples"
    assert {row[0] for row in _rows(8)} == expected


def test_query_9_reports_every_produced_type():
    """Counted from the triples directly, not from the query's own output."""
    expected = {
        (method, produced)
        for method, produced in ONTOLOGY.subject_objects(OOP.producesType)
        if (method, RDF.type, OOP.Method) in ONTOLOGY
    }

    assert expected
    assert {(row[0], row[2]) for row in _rows(9)} == expected


def test_query_10_reports_every_thrown_error():
    """Same check for oop:throwsError."""
    expected = {
        (method, error)
        for method, error in ONTOLOGY.subject_objects(OOP.throwsError)
        if (method, RDF.type, OOP.Method) in ONTOLOGY
    }

    assert expected
    assert {(row[0], row[2]) for row in _rows(10)} == expected


def test_query_2_covers_every_named_individual():
    """66 named individuals, the figure reported in README.md and report.md."""
    individuals = {row[0] for row in _rows(2)}
    from_triples = set(ONTOLOGY.subjects(RDF.type, OWL.NamedIndividual))

    assert individuals == from_triples
    assert len(individuals) == 66


def test_query_5_returns_both_directions_of_its_entity():
    """Query 5 lists incoming and outgoing relations, tagged with a direction.

    The graph service makes the same promise, so the query it was modelled on
    should demonstrably keep it.
    """
    directions = {str(row[2]) for row in _rows(5)}
    assert directions == {"outgoing", "incoming"}
