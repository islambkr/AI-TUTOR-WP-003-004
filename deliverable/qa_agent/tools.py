"""tools.py -- Step 5 of AI-TUTOR-WP-003: the LangChain tool layer.

These are thin wrappers. All query logic lives in graph_service.py; a tool only
adapts the result for the model and passes it back.

Two things are deliberate here.

1. Docstrings are written for the model, not for a developer, because the model
   reads them to choose a tool. They avoid naming any real entity: a small model
   copies example values straight into its tool arguments.

2. Tool results are COMPACT projections of the service records. The service
   returns the full record the work package requires (IRI, identifier, label,
   relation). The model needs far less, and the difference matters: the full
   record for one entity costs about 900 tokens against a 4096-token context,
   which overflows and makes a small model incoherent. The projection keeps the
   "statement" strings, which already contain both labels and both identifiers.
"""

from langchain_core.tools import tool

import graph_service


def _is_problem(result) -> bool:
    """True when the service returned a not_found / ambiguous / no_path record."""
    if isinstance(result, dict):
        return result.get("status") != "ok"
    return bool(result) and result[0].get("status") != "ok"


@tool
def describe_ontology_entity(label_or_id: str) -> dict:
    """Return what the ontology records about one entity of the COMP101 OOP lecture.

    Use for "what is X?" questions.

    Pass label_or_id exactly as the student wrote it. Never substitute an entity
    named anywhere else, including in these instructions.

    Result "status":
      ok        -> "definition", plus "facts": sentences that already contain
                   both labels and both identifiers. Quote them as written.
      not_found -> the ontology has no such entity. Say so; do not answer from
                   your own knowledge.
      ambiguous -> "matches" lists candidates. Ask which one is meant.
    """
    record = graph_service.describe_entity(label_or_id)

    if _is_problem(record):
        return record

    attributes = record["attributes"]
    return {
        "status": "ok",
        "entity": record["citation"],
        "kind": record["kind"],
        "types": record["types"],
        "definition": attributes.get("definition", ""),
        "notes": {
            key: value
            for key, value in attributes.items()
            if key not in ("definition", "courseId")
        },
        "facts": [relation["statement"] for relation in record["relations"]],
    }


@tool
def find_concept_dependencies(
    label_or_id: str,
    include_transitive: bool = False,
    direction: str = "depends_on",
) -> dict:
    """Return prerequisites from the ontology (the dependsOn relation only).

    Use ONLY for "what does X depend on", "what depends on X", "what are the
    prerequisites of X".

    Do NOT use for other relations. What X enables, contrasts with, produces,
    throws or is part of are different relations; use find_named_relation.

    direction:  "depends_on" = what X needs;  "required_by" = what needs X.
    include_transitive:  true follows the chain, so a prerequisite of a
    prerequisite is reported too.

    When "status" is ok, "facts" holds sentences containing both labels and
    both identifiers -- quote them as written. "indirect" lists the ones reached
    only through a chain. A "count" of 0 means the ontology records no
    prerequisites; say so rather than supplying your own.
    """
    results = graph_service.get_dependencies(
        label_or_id,
        transitive=include_transitive,
        direction=direction,
    )

    if _is_problem(results):
        return results[0]

    return {
        "status": "ok",
        "query": label_or_id,
        "direction": direction,
        "count": len(results),
        "facts": [record["statement"] for record in results],
        "indirect": [
            record["citation"] for record in results if not record["direct"]
        ],
    }


@tool
def find_named_relation(label_or_id: str, relation: str) -> dict:
    """Return what one entity is linked to by ONE named relation.

    Use whenever the question names a relation other than dependency.

    The entity you pass is always the SUBJECT of the relation, so direction
    matters: a property and its opposite answer different questions.

      "what contrasts with X"     -> relation="contrastsWith"
      "what enables X"            -> relation="enabledBy"
      "what does X enable"        -> relation="enables"
      "what type does X produce"  -> relation="producesType"
      "which error can X throw"   -> relation="throwsError"
      "what are the parts of X"   -> relation="hasPart"
      "what is X part of"         -> relation="partOf"
      "what are examples of X"    -> relation="hasExample"
      "what is X an example of"   -> relation="exampleOf"
      "what implements X"         -> relation="implementedBy"
      "what does X implement"     -> relation="implements"

    X is a placeholder. Pass the entity from the student's question, never one
    named in these instructions.

    When "status" is ok, "facts" holds sentences containing both labels and both
    identifiers -- quote them as written. A "count" of 0 means the ontology
    records that relation nowhere for this entity: say so plainly, do not
    substitute another relation, and do not answer from your own knowledge.
    """
    results = graph_service.get_relations_by_name(label_or_id, relation)

    if _is_problem(results):
        return results[0]

    response = {
        "status": "ok",
        "query": label_or_id,
        "relation": relation,
        "count": len(results),
        "facts": [record["statement"] for record in results],
    }

    if not results:
        response["available_relations"] = sorted(
            {record["predicate"] for record in graph_service.get_relations(label_or_id)}
        )

    return response


@tool
def find_relation_path(source: str, target: str) -> dict:
    """Return one chain of relations connecting two entities.

    Use for "how is X connected to Y" or "show a path from X to Y".

    When "status" is ok, "steps" holds the chain in order, each already a
    sentence containing both labels and both identifiers. Report them in order,
    as written; do not compress them into a claim the ontology does not make.

      no_path   -> both entities exist but nothing connects them. Say so.
      not_found -> one of them is not in the ontology.
      ambiguous -> "matches" lists candidates; ask which is meant.
    """
    record = graph_service.find_path(source, target)

    if _is_problem(record):
        return record

    return {
        "status": "ok",
        "from": record["source"]["citation"],
        "to": record["target"]["citation"],
        "length": record["length"],
        "steps": [step["statement"] for step in record["steps"]],
    }


@tool
def list_lecture_entities(type_label: str) -> dict:
    """List every entity of one category covered by the lecture.

    Use for "which X are covered in this lecture", "list all X".

    Categories (plural and lower case accepted): Algorithm, BuiltInFunction,
    ClassMember, Concept, DataType, DesignAbstraction, ErrorType,
    ImplementorType, LanguageConstruct, Lecture, Method, MethodRole,
    OOPMechanism, PythonInternals, Skill, TypeProducer.

    When "status" is ok, "entities" holds names that already include their
    identifiers -- list them as written. A "count" of 0 means the category
    exists but holds nothing; name none yourself. "not_found" means no such
    category.
    """
    results = graph_service.list_entities_by_type(type_label)

    if _is_problem(results):
        problem = dict(results[0])
        problem["available_types"] = [
            record["id"] for record in graph_service.list_classes()
        ]
        return problem

    return {
        "status": "ok",
        "query": type_label,
        "count": len(results),
        "entities": [
            f"{record['label']} ({record['id']})" for record in results
        ],
    }


# The tools given to the agent. The first three are named in the work package.
# find_named_relation and list_lecture_entities were added after evaluation:
# without them, questions about a specific relation were answered with the
# dependency tool, and "which errors are covered?" had no tool at all.
GRAPH_TOOLS = [
    describe_ontology_entity,
    find_concept_dependencies,
    find_relation_path,
    find_named_relation,
    list_lecture_entities,
]