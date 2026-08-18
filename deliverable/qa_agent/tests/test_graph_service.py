"""Deterministic unit tests for graph_service.py (AI-TUTOR-WP-003, step 4).

No LLM is involved. Every expected value below was read from the ontology
itself, so a failure means either the code or the ontology changed.

Run with:   .venv/bin/python -m pytest tests/ -v
"""

import graph_service
from graph_service import (
    describe_entity,
    find_entity,
    find_path,
    get_dependencies,
    get_relations,
    get_relations_by_name,
    relation_names,
    list_classes,
    list_entities_by_type,
)
from rdflib.namespace import OWL, RDF

REPR_IRI = "http://comp101.sase.um6p.ma/ontology/oop#MOOP003"

# The ontology declares 18 owl:Class nodes: 16 named ones plus 2 anonymous
# owl:unionOf expressions (TypeProducer and ImplementorType are defined as
# unions), which are blank nodes and must not be reported.
EXPECTED_CLASS_COUNT = 16


# --------------------------------------------------------------- list_classes


def test_list_classes_returns_every_named_class():
    assert len(list_classes()) == EXPECTED_CLASS_COUNT


def test_list_classes_skips_anonymous_classes():
    """Blank-node class expressions have no IRI, so none may appear."""
    for record in list_classes():
        assert record["iri"].startswith("http://comp101.sase.um6p.ma/ontology/oop#")


def test_list_classes_records_have_the_agreed_shape():
    for record in list_classes():
        assert record["status"] == "ok"
        assert set(record) == {"status", "iri", "id", "label", "comment"}
        assert record["id"]
        assert record["label"]


def test_list_classes_is_sorted_and_repeatable():
    """Sorting is what makes the output deterministic across runs."""
    first = list_classes()
    assert first == sorted(first, key=lambda record: record["id"])
    assert first == list_classes()


def test_list_classes_contains_a_known_class():
    methods = [record for record in list_classes() if record["id"] == "Method"]
    assert len(methods) == 1
    assert methods[0]["label"] == "Method"


# ------------------------------------------------------ list_entities_by_type


def test_list_entities_by_type_returns_the_five_methods():
    records = list_entities_by_type("Method")
    assert {record["label"] for record in records} == {
        "__init__",
        "__str__",
        "__repr__",
        "__eq__",
        "__len__",
    }


def test_list_entities_by_type_is_sorted_by_course_id():
    """Records come back ordered by courseId, which is what makes runs repeatable."""
    ids = [record["id"] for record in list_entities_by_type("Method")]
    assert ids == ["MOOP001", "MOOP002", "MOOP003", "MOOP004", "MOOP005"]


def test_list_entities_by_type_records_carry_id_label_and_type():
    for record in list_entities_by_type("DataType"):
        assert record["status"] == "ok"
        assert record["type"] == "DataType"
        assert record["id"]
        assert record["label"]


def test_list_entities_by_type_ignores_case():
    """The work package requires handling a label that differs only by case."""
    assert list_entities_by_type("datatype") == list_entities_by_type("DataType")
    assert list_entities_by_type("  DATATYPE  ") == list_entities_by_type("DataType")


def test_list_entities_by_type_empty_class_returns_empty_list():
    """Algorithm is declared but has no asserted individuals.

    An empty list means "the class exists and holds nothing", which is a
    different answer from "there is no such class".
    """
    assert list_entities_by_type("Algorithm") == []


def test_list_entities_by_type_unknown_class_reports_not_found():
    result = list_entities_by_type("Algorythm")
    assert len(result) == 1
    assert result[0]["status"] == "not_found"
    assert result[0]["query"] == "Algorythm"


# ---------------------------------------------------------------- find_entity


def test_find_entity_by_label():
    matches = find_entity("__repr__")
    assert len(matches) == 1
    assert matches[0]["iri"] == REPR_IRI
    assert matches[0]["matched_by"] == "label"


def test_find_entity_by_course_id():
    matches = find_entity("MOOP003")
    assert len(matches) == 1
    assert matches[0]["iri"] == REPR_IRI
    assert matches[0]["matched_by"] == "courseId"


def test_find_entity_by_iri():
    matches = find_entity(REPR_IRI)
    assert len(matches) == 1
    assert matches[0]["matched_by"] == "iri"


def test_find_entity_ignores_case_and_whitespace():
    """All four spellings must land on the same entity."""
    for probe in ["MOOP003", "mooP003", "  moop003  ", "__REPR__"]:
        matches = find_entity(probe)
        assert len(matches) == 1, probe
        assert matches[0]["iri"] == REPR_IRI, probe


def test_find_entity_reports_a_case_only_difference():
    """The agent should be able to say which entity it assumed."""
    assert find_entity("__repr__")[0]["matched_by"] == "label"
    assert find_entity("__REPR__")[0]["matched_by"] == "label (different case)"


def test_find_entity_prefers_an_exact_match_over_partial_ones():
    """"Class" is one individual's label but a substring of ten others.

    Tier 1 must win, otherwise a common question becomes ambiguous for no
    reason.
    """
    matches = find_entity("Class")
    assert len(matches) == 1
    assert matches[0]["label"] == "Class"
    assert matches[0]["id"] == "COOP001"


def test_find_entity_returns_several_when_only_partial_matches_exist():
    labels = {record["label"] for record in find_entity("abstract")}
    assert labels == {
        "Abstract Class",
        "Abstract Method",
        "Abstraction",
        "DesignAbstraction",
    }
    assert all(record["matched_by"] == "partial label" for record in find_entity("abstract"))


def test_find_entity_finds_classes_as_well_as_individuals():
    matches = find_entity("MethodRole")
    assert len(matches) == 1
    assert matches[0]["kind"] == "class"


def test_find_entity_unknown_text_reports_not_found():
    result = find_entity("gradient descent")
    assert len(result) == 1
    assert result[0]["status"] == "not_found"
    assert result[0]["query"] == "gradient descent"


def test_find_entity_rejects_empty_input():
    assert find_entity("   ")[0]["status"] == "not_found"


# ------------------------------------------------------------ describe_entity


def test_describe_entity_returns_identity_attributes_and_relations():
    record = describe_entity("Encapsulation")
    assert record["status"] == "ok"
    assert record["id"] == "COOP_ENC"
    assert record["label"] == "Encapsulation"
    assert record["kind"] == "individual"
    assert record["types"] == ["Concept"]
    assert "attributes" in record
    assert "relations" in record


def test_describe_entity_includes_the_definition():
    """The agent answers "What is X?" from this field, so it must be present."""
    attributes = describe_entity("Encapsulation")["attributes"]
    assert attributes["definition"].startswith("Bundling data and behaviour")
    assert attributes["cognitiveType"] == "conceptual"
    assert attributes["courseId"] == "COOP_ENC"


def test_describe_entity_can_be_reached_by_course_id():
    """Resolution is shared, so every lookup form must give the same record."""
    assert describe_entity("COOP_ENC") == describe_entity("Encapsulation")


def test_describe_entity_reports_ambiguity_with_candidates():
    record = describe_entity("abstract")
    assert record["status"] == "ambiguous"
    assert record["query"] == "abstract"
    assert len(record["matches"]) == 4
    # The candidates must be usable as follow-up queries by the agent.
    for candidate in record["matches"]:
        assert candidate["label"]
        assert candidate["id"]


def test_describe_entity_reports_not_found():
    record = describe_entity("gradient descent")
    assert record["status"] == "not_found"
    assert record["query"] == "gradient descent"


def test_describe_entity_works_for_a_class():
    record = describe_entity("MethodRole")
    assert record["status"] == "ok"
    assert record["kind"] == "class"


# -------------------------------------------------------------- get_relations


def test_get_relations_lists_the_four_facts_about_repr():
    relations = get_relations("__repr__")
    assert {(r["predicate"], r["label"]) for r in relations} == {
        ("exampleOf", "Dunder Method"),
        ("producesType", "str"),
        ("taughtIn", "Object-Oriented Programming"),
        ("throwsError", "TypeError"),
    }


def test_get_relations_collapses_inverse_pairs():
    """__repr__ producesType str and str isProducedBy __repr__ are one fact.

    The ontology asserts both halves of every inverse pair, so without
    collapsing, every relation would be reported twice.
    """
    relations = get_relations("__repr__")
    predicates = [relation["predicate"] for relation in relations]
    assert "producesType" in predicates
    assert "isProducedBy" not in predicates
    assert len(relations) == 4


def test_get_relations_reports_symmetric_relations_once():
    relations = get_relations("Encapsulation")
    contrasts = [r for r in relations if r["predicate"] == "contrastsWith"]
    assert len(contrasts) == 1
    assert contrasts[0]["direction"] == "symmetric"


def test_get_relations_keeps_facts_that_are_only_asserted_incoming():
    """Collapsing must not hide information, only state it once."""
    labels = {r["label"] for r in get_relations("Encapsulation")}
    assert "Data Hiding" in labels      # Data Hiding dependsOn Encapsulation
    assert "Abstraction" in labels      # Abstraction dependsOn Encapsulation


def test_get_relations_loses_no_neighbour_for_any_individual():
    """The safety net for inverse collapsing, checked across all 66 individuals."""
    for individual in graph_service.GRAPH.subjects(RDF.type, OWL.NamedIndividual):
        neighbours = set()
        for predicate, other in graph_service.GRAPH.predicate_objects(individual):
            if predicate in graph_service.OBJECT_PROPERTIES:
                neighbours.add(str(other))
        for other, predicate in graph_service.GRAPH.subject_predicates(individual):
            if predicate in graph_service.OBJECT_PROPERTIES:
                neighbours.add(str(other))
        reported = {r["iri"] for r in graph_service._relations_of(individual)}
        assert neighbours == reported, graph_service._label_of(individual)


def test_get_relations_records_carry_iri_id_and_label():
    for relation in get_relations("Encapsulation"):
        assert relation["iri"].startswith("http://")
        assert relation["id"]
        assert relation["label"]
        assert relation["direction"] in ("outgoing", "incoming", "symmetric")


def test_get_relations_reports_not_found_inside_a_list():
    result = get_relations("gradient descent")
    assert len(result) == 1
    assert result[0]["status"] == "not_found"


# ----------------------------------------------------------- get_dependencies


def test_get_dependencies_direct_only_by_default():
    labels = {record["label"] for record in get_dependencies("Data Hiding")}
    assert labels == {"Encapsulation", "Name Mangling"}


def test_get_dependencies_transitive_follows_the_chain():
    """Data Hiding -> Encapsulation -> Class, so Class appears only when
    transitive=True. The "+" in the property path is what walks the chain;
    the owl:TransitiveProperty declaration alone would not."""
    direct = {record["label"] for record in get_dependencies("Data Hiding")}
    deep = {record["label"] for record in get_dependencies("Data Hiding", transitive=True)}
    assert "Class" not in direct
    assert "Class" in deep
    assert direct < deep          # every direct dependency is also a transitive one


def test_get_dependencies_marks_direct_versus_indirect():
    records = get_dependencies("Data Hiding", transitive=True)
    by_label = {record["label"]: record["direct"] for record in records}
    assert by_label["Encapsulation"] is True
    assert by_label["Class"] is False


def test_get_dependencies_direct_ones_are_listed_first():
    records = get_dependencies("Data Hiding", transitive=True)
    flags = [record["direct"] for record in records]
    assert flags == sorted(flags, reverse=True)


def test_get_dependencies_reverse_direction():
    """Answers "What concepts depend on Class?", required by section 6."""
    labels = {
        record["label"]
        for record in get_dependencies("Class", direction="required_by")
    }
    assert labels == {"Encapsulation", "Inheritance", "Instantiation", "Object"}


def test_get_dependencies_never_returns_the_entity_itself():
    for record in get_dependencies("Class", transitive=True, direction="required_by"):
        assert record["label"] != "Class"


def test_get_dependencies_empty_when_none_are_recorded():
    """__repr__ has no dependsOn edges. Empty is a true answer, not a failure."""
    assert get_dependencies("__repr__") == []


def test_get_dependencies_rejects_an_invalid_direction():
    """The LLM chooses this argument, so it will sometimes get it wrong."""
    result = get_dependencies("Class", direction="sideways")
    assert result[0]["status"] == "not_found"


def test_get_dependencies_reports_not_found_inside_a_list():
    result = get_dependencies("gradient descent")
    assert len(result) == 1
    assert result[0]["status"] == "not_found"


# ------------------------------------------------------------------ find_path


def test_find_path_connects_class_to_data_hiding():
    """The example named in section 6 of the work package."""
    result = find_path("Class", "Data Hiding")
    assert result["status"] == "ok"
    assert result["length"] == 2
    assert [step["predicate"] for step in result["steps"]] == ["dependsOn", "dependsOn"]
    assert result["steps"][0]["from"] == "Class"
    assert result["steps"][-1]["to"] == "Data Hiding"


def test_find_path_steps_form_an_unbroken_chain():
    """Each step must start where the previous one ended."""
    result = find_path("Class", "Data Hiding")
    for earlier, later in zip(result["steps"], result["steps"][1:]):
        assert earlier["to"] == later["from"]


def test_find_path_avoids_the_lecture_hub():
    """oop:teaches links L10 to all 65 individuals, making every pair two hops
    apart through the lecture. That path is true but says nothing, so the
    search must not use it."""
    result = find_path("Class", "Data Hiding")
    predicates = [step["predicate"] for step in result["steps"]]
    assert "teaches" not in predicates
    assert "taughtIn" not in predicates


def test_find_path_to_itself_is_length_zero():
    result = find_path("Class", "Class")
    assert result["status"] == "ok"
    assert result["length"] == 0
    assert result["steps"] == []


def test_find_path_respects_max_depth():
    """Both entities exist, but not within one hop -- the work package's
    "path does not exist within the depth limit" condition."""
    result = find_path("__repr__", "Metaclass", max_depth=1)
    assert result["status"] == "no_path"
    assert "source" in result and "target" in result


def test_find_path_is_deterministic():
    """Several shortest paths may exist; the same one must be chosen each time."""
    assert find_path("Class", "Data Hiding") == find_path("Class", "Data Hiding")


def test_find_path_reports_an_unknown_endpoint():
    assert find_path("Class", "gradient descent")["status"] == "not_found"
    assert find_path("gradient descent", "Class")["status"] == "not_found"


def test_find_path_reports_an_ambiguous_endpoint():
    assert find_path("abstract", "Class")["status"] == "ambiguous"


def test_empty_and_not_found_are_distinguishable():
    """The distinction the agent depends on, asserted explicitly."""
    existing_but_empty = list_entities_by_type("Algorithm")
    missing = list_entities_by_type("Algorythm")
    assert existing_but_empty == []
    assert missing != []
    assert missing[0]["status"] == "not_found"


# ------------------------------------------------------ get_relations_by_name


def test_relation_names_lists_every_object_property():
    names = relation_names()
    assert "dependsOn" in names
    assert "contrastsWith" in names
    assert "enabledBy" in names
    assert names == sorted(names)


def test_get_relations_by_name_filters_to_one_relation():
    statements = [r["statement"] for r in get_relations_by_name("Inheritance", "contrastsWith")]
    assert statements == [
        "Inheritance (COOP013) contrastsWith Composition (DA_OOP03)",
        "Inheritance (COOP013) contrastsWith Interface (DA_OOP02)",
    ]


def test_get_relations_by_name_respects_direction():
    """A property and its inverse ask different questions.

    The ontology asserts "Method Overriding enables Polymorphism". Asking for
    "enables" must return it; asking for "enabledBy" must return nothing,
    because nothing enables Method Overriding. Collapsing the two would answer
    the opposite question while looking correct.
    """
    forwards = get_relations_by_name("Method Overriding", "enables")
    backwards = get_relations_by_name("Method Overriding", "enabledBy")
    assert [r["statement"] for r in forwards] == [
        "Method Overriding (OM_OOP04) enables Polymorphism (COOP018)"
    ]
    assert backwards == []


def test_get_relations_by_name_finds_a_fact_asserted_from_the_other_end():
    """Direction is respected, but the inverse spelling is still consulted.

    "Instantiation enabledBy Constructor" is asserted; so is its inverse
    "Constructor enables Instantiation". Either assertion satisfies the
    question "what is Instantiation enabled by?".
    """
    assert [r["statement"] for r in get_relations_by_name("Instantiation", "enabledBy")] == [
        "Instantiation (COOP007) enabledBy Constructor (OM_OOP01)"
    ]
    assert get_relations_by_name("Instantiation", "enables") == []


def test_get_relations_by_name_never_returns_the_inverse_predicate():
    """Across the whole ontology, a request for P returns only P."""
    import graph_service as gs

    for prop in gs.OBJECT_PROPERTIES:
        name = gs._local_name(prop)
        for individual in gs.GRAPH.subjects(RDF.type, OWL.NamedIndividual):
            for record in get_relations_by_name(individual, name):
                assert record["predicate"] == name


def test_get_relations_by_name_does_not_leak_other_relations():
    """Class is a dependency of Instantiation but does not enable it."""
    labels = {r["label"] for r in get_relations_by_name("Instantiation", "enabledBy")}
    assert labels == {"Constructor"}
    assert "Class" not in labels


def test_get_relations_by_name_empty_when_relation_is_absent():
    assert get_relations_by_name("__repr__", "contrastsWith") == []


def test_get_relations_by_name_rejects_an_unknown_relation():
    result = get_relations_by_name("Class", "frobnicates")
    assert result[0]["status"] == "not_found"
    assert "Available" in result[0]["message"]


def test_get_relations_by_name_reports_an_unknown_entity():
    assert get_relations_by_name("gradient descent", "enables")[0]["status"] == "not_found"


def test_get_relations_by_name_agrees_with_the_raw_graph():
    """Every returned fact must exist as a triple, in the direction claimed."""
    import graph_service as gs
    from rdflib import URIRef

    for name in ("hasPart", "partOf", "enables", "enabledBy", "producesType"):
        prop = next(p for p in gs.OBJECT_PROPERTIES if gs._local_name(p) == name)
        inverse = gs.INVERSE_OF.get(prop)
        for individual in gs.GRAPH.subjects(RDF.type, OWL.NamedIndividual):
            for record in get_relations_by_name(individual, name):
                other = URIRef(record["iri"])
                asserted = (individual, prop, other) in gs.GRAPH
                asserted_inverse = (
                    inverse is not None and (other, inverse, individual) in gs.GRAPH
                )
                assert asserted or asserted_inverse, record["statement"]


# ------------------------------- the five conditions named in section 5.4 ----
# Each condition gets one test that states it plainly, so the requirement can
# be traced to the code that satisfies it.


def test_condition_1_no_entity_matches_the_input():
    assert describe_entity("gradient descent")["status"] == "not_found"


def test_condition_2_more_than_one_entity_matches_the_input():
    record = describe_entity("abstract")
    assert record["status"] == "ambiguous"
    assert len(record["matches"]) > 1


def test_condition_3_entity_has_no_value_for_the_relation():
    """Distinct from "not found": the entity exists, the answer is empty."""
    assert get_dependencies("__repr__") == []
    assert describe_entity("__repr__")["status"] == "ok"


def test_condition_4_path_does_not_exist_within_the_depth_limit():
    assert find_path("__repr__", "Metaclass", max_depth=1)["status"] == "no_path"


def test_condition_5_label_differs_only_by_case():
    assert find_entity("__REPR__")[0]["iri"] == REPR_IRI
    assert find_entity("__REPR__")[0]["matched_by"] == "label (different case)"


# ------------------------------------------------- module-wide guarantees ----


def test_every_record_carries_a_status():
    """The uniform return contract: callers never have to guess the shape."""
    single_records = [
        describe_entity("Encapsulation"),
        describe_entity("nothing at all"),
        find_path("Class", "Data Hiding"),
    ]
    list_results = [
        list_classes(),
        list_entities_by_type("Method"),
        find_entity("Class"),
        get_relations("__repr__"),
        get_dependencies("Data Hiding"),
    ]
    for record in single_records:
        assert "status" in record
    for results in list_results:
        for record in results:
            assert "status" in record


def test_results_are_json_serialisable():
    """Tool results are serialised to JSON at the LangChain boundary, so no
    rdflib term may survive in a record."""
    import json

    json.dumps(
        {
            "classes": list_classes(),
            "entities": list_entities_by_type("Method"),
            "found": find_entity("abstract"),
            "described": describe_entity("Encapsulation"),
            "relations": get_relations("__repr__"),
            "dependencies": get_dependencies("Data Hiding", transitive=True),
            "path": find_path("Class", "Data Hiding"),
        }
    )


def test_repeated_calls_return_identical_results():
    """Determinism, the headline requirement for the graph service."""
    for _ in range(3):
        assert list_classes() == list_classes()
        assert describe_entity("Encapsulation") == describe_entity("Encapsulation")
        assert find_path("Class", "Data Hiding") == find_path("Class", "Data Hiding")
