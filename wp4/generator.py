"""generator.py -- Step 5 of WP-004: structured generation inside the gate.

The model is given the item, the requested instance type, and the evidence the
gate permits -- never the ontology. That restriction is the point of the work
package: the gate has already decided what may be drawn on, so the model's job
is wording, not scope.

Two choices worth stating, because both shape the numbers:

Sampling picks a relation *role* first and then a triple within it, rather than
sampling triples directly. `definition` supplies 36% of all evidence and is
permitted by every item, so uniform sampling would make most candidates
explanations. Direction is canonicalised at the same time: an inverse pair is
one edge, and drawing both spellings would produce the same question twice --
32% of the evidence is a redundant half. See relation_policy.md sections 3 and 4.

The model is asked for the concrete variant, not the union. A discriminated
union compiles to `oneOf`, which small local models fill unreliably, and the
generator already knows which type it requested.

Run it:
    python -m wp4.generator                       one candidate per type, ITEM-001
    python -m wp4.generator ITEM-013 --n 3        three of each for another item
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

from langchain_ollama import ChatOllama
from pydantic import ValidationError

from . import scope_gate, validator
from .schemas import (
    INSTANCE_MODELS,
    CandidateRecord,
    EvidenceTriple,
    GenerationInput,
    InstanceType,
    Item,
    OntologyScope,
)

# qwen3, not WP-003's gemma4:e2b-mlx. gemma4 cannot produce structured output
# at all: across three prompt formulations and method="json_schema" it returned
# plain "key: value" text every time, and once reproduced the prompt's own field
# layout verbatim rather than filling it. The same call against qwen3 parsed
# first try. Section 9 of the work package requires structured output, so this
# is a capability requirement rather than a preference. Measured in
# evaluation_report.md.
MODEL_NAME = "qwen3:latest"
TEMPERATURE = 0.4  # not 0: nine candidates per item must not be nine copies
NUM_CTX = 8192

INSTRUCTIONS = {
    "short_answer": (
        "Write one short-answer question and its model answer. The answer should "
        "be one or two sentences of prose."
    ),
    "true_false": (
        "Write one statement that is either true or false, and give the answer as "
        "exactly 'true' or 'false'. Make roughly half of the statements false by "
        "altering a detail of the evidence."
    ),
    "mcq": (
        "Write one multiple-choice question with exactly four distinct choices, "
        "one of which is correct. Write each choice as plain text with no letter "
        "or number in front of it, and make answer_key the full text of the "
        "correct choice rather than a letter. The wrong choices should be "
        "plausible to a student who has not learned this material."
    ),
}

PROMPT = """You write assessment questions for a Python programming course.

LEARNING ITEM
{item_id}: {title}
{description}

FACTS YOU MAY USE. Use only these. Do not use any other programming concept,
even if it is true, and do not mention any term that does not appear below.
{evidence}

TASK
{instruction}

Set item_id to {item_id}. For answer_key, give {answer_shape}. In
ontology_entities_used, list only the identifiers of the facts you used -- the
text inside the round brackets above, and nothing else.
"""

# The field list used to be laid out in two aligned columns. The model copied
# the layout instead of filling it, returning that table as plain text rather
# than JSON -- the same defect WP-003 recorded, where concrete examples in a
# prompt are reproduced verbatim by a small model. Prose avoids giving it a
# shape to imitate; the schema already carries the field names.

ANSWER_SHAPE = {
    "short_answer": "the model answer in one or two sentences",
    "true_false": "exactly the word true or the word false",
    "mcq": "the correct choice, copied character for character from choices",
}


def render_evidence(evidence: list[EvidenceTriple]) -> str:
    """The facts, one per line, with identifiers spelled out.

    The identifier is repeated beside every label because WP-003 recorded this
    model garbling underscore-heavy names when it had to recall them: giving it
    the string to copy is more reliable than asking it to reproduce one.
    """
    lines = []
    for triple in evidence:
        subject = validator.LABELS.get(triple.subject, triple.subject)
        if triple.predicate == "definition":
            lines.append(f"- {subject} ({triple.subject}) is defined as: {triple.object}")
        else:
            obj = validator.LABELS.get(triple.object, triple.object)
            lines.append(
                f"- {subject} ({triple.subject}) {triple.predicate} "
                f"{obj} ({triple.object})"
            )
    return "\n".join(lines)


def canonical_edge(triple: EvidenceTriple) -> tuple:
    """One key per underlying edge, whichever direction it is written in.

    `A hasPart B` and `B partOf A` are the same fact. Without this the sampler
    treats them as two, and a third of the evidence is a redundant half.
    """
    inverse = scope_gate.graph_service.INVERSE_OF.get(
        scope_gate.graph_service.OOP[triple.predicate]
    )
    if inverse is None:
        return tuple(sorted([(triple.subject, triple.object)])) + (triple.predicate,)
    other = scope_gate.graph_service._local_name(inverse)
    return tuple(
        sorted(
            [
                (triple.subject, triple.predicate, triple.object),
                (triple.object, other, triple.subject),
            ]
        )
    )


def select_evidence(
    scope: OntologyScope, count: int = 4, rng: random.Random | None = None
) -> list[EvidenceTriple]:
    """Choose a few facts: relation role first, then a triple within it.

    Sampling triples directly would hand the model mostly definitions, which are
    36% of all evidence and present for every item. Choosing the role first
    gives the rarer relations -- throwsError, producesType -- a real chance of
    appearing, which is what makes the instance types come out mixed.
    """
    rng = rng or random.Random()

    by_relation: dict[str, list[EvidenceTriple]] = {}
    seen: set = set()
    for triple in scope.evidence:
        edge = canonical_edge(triple)
        if edge in seen:
            continue
        seen.add(edge)
        by_relation.setdefault(triple.predicate, []).append(triple)

    chosen: list[EvidenceTriple] = []
    relations = list(by_relation)
    rng.shuffle(relations)
    for relation in relations:
        if len(chosen) >= count:
            break
        chosen.append(rng.choice(by_relation[relation]))

    return chosen


def build_input(
    item: Item,
    scope: OntologyScope,
    instance_type: InstanceType,
    rng: random.Random | None = None,
    model_name: str = MODEL_NAME,
) -> GenerationInput:
    return GenerationInput(
        item_id=item.id,
        item_title=item.title,
        item_description=item.description,
        instance_type=instance_type,
        allowed_entities=sorted(scope.allowed_entities),
        allowed_relations=sorted(scope.allowed_relations),
        evidence=select_evidence(scope, rng=rng),
        model_name=model_name,
    )


def build_model(model_name: str = MODEL_NAME, temperature: float = TEMPERATURE):
    return ChatOllama(model=model_name, temperature=temperature, num_ctx=NUM_CTX)


def generate_one(
    item: Item,
    scope: OntologyScope,
    instance_type: InstanceType,
    llm=None,
    rng: random.Random | None = None,
) -> CandidateRecord:
    """Ask for one candidate, validate it, and record everything either way.

    A candidate that fails to parse is kept with its raw output and its reason.
    Section 10.7 requires rejected candidates to stay in the dataset, and a
    malformed one is the most informative kind to keep.
    """
    llm = llm or build_model()
    generation_input = build_input(item, scope, instance_type, rng=rng)

    prompt = PROMPT.format(
        item_id=item.id,
        title=item.title,
        description=item.description,
        evidence=render_evidence(generation_input.evidence),
        instruction=INSTRUCTIONS[instance_type],
        answer_shape=ANSWER_SHAPE[instance_type],
    )

    # json_schema rather than the default: it constrains decoding to the
    # schema instead of asking the model to produce JSON unaided, which is
    # what this 5B model failed at.
    structured = llm.with_structured_output(
        INSTANCE_MODELS[instance_type], method="json_schema"
    )

    try:
        instance = structured.invoke(prompt)
    except (ValidationError, ValueError, TypeError) as error:
        return CandidateRecord(
            generation_input=generation_input,
            raw_output=str(error)[:2000],
            rejection_reason=f"malformed output: {type(error).__name__}",
        )

    # The model is given the evidence and rarely echoes it back. When it cites
    # nothing, the generator attaches what it supplied, because that is what the
    # candidate was actually built from -- and flags it, since the
    # fabricated-citation check then has nothing of the model's own to judge.
    attached = False
    if not instance.ontology_evidence:
        instance = instance.model_copy(
            update={"ontology_evidence": generation_input.evidence}
        )
        attached = True

    verdict = validator.validate_candidate(instance, item, scope)
    return CandidateRecord(
        generation_input=generation_input,
        instance=instance,
        ontology_validation=verdict,
        ungrounded_distractors=validator.ungrounded_distractors(instance, scope),
        evidence_attached=attached,
        rejection_reason=None if verdict.passed else "; ".join(verdict.failures),
    )


def generate_for_item(
    item: Item, per_type: int = 3, llm=None, seed: int | None = None
) -> list[CandidateRecord]:
    scope = scope_gate.build_scope(item)
    llm = llm if llm is not None else build_model()
    rng = random.Random(seed)

    records = []
    for instance_type in ("short_answer", "true_false", "mcq"):
        for _ in range(per_type):
            records.append(generate_one(item, scope, instance_type, llm, rng))
    return records


def write_records(records: list[CandidateRecord], path: Path) -> None:
    """One JSON object per line, rejects included."""
    with path.open("w") as handle:
        for record in records:
            handle.write(record.model_dump_json() + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("item", nargs="?", default="ITEM-001")
    parser.add_argument("--n", type=int, default=1, help="candidates per type")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--model", default=MODEL_NAME)
    args = parser.parse_args()

    items = scope_gate.load_items()
    matches = [i for key, i in items.items() if args.item in key]
    if not matches:
        sys.exit(f"no item matching {args.item!r}")
    item = matches[0]

    print(f"{item}\nmodel: {args.model}, {args.n} per type\n")
    started = time.time()
    records = generate_for_item(
        item, per_type=args.n, llm=build_model(args.model), seed=args.seed
    )

    for record in records:
        instance = record.instance
        mark = "pass" if record.passed_ontology else "FAIL"
        kind = record.generation_input.instance_type
        print(f"[{mark}] {kind}")
        if instance is None:
            print(f"    could not parse: {record.rejection_reason}")
            continue
        print(f"    Q: {instance.prompt}")
        print(f"    A: {instance.answer_key}")
        if getattr(instance, "choices", None):
            print(f"    choices: {instance.choices}")
        if record.rejection_reason:
            print(f"    rejected: {record.rejection_reason}")

    passed = sum(1 for r in records if r.passed_ontology)
    print(f"\n{passed}/{len(records)} passed ontology validation "
          f"in {time.time() - started:.0f}s")

    if args.out:
        write_records(records, args.out)
        print(f"written to {args.out}")


if __name__ == "__main__":
    main()
