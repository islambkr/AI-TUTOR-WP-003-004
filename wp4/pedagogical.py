"""pedagogical.py -- Step 7 of WP-004: the model reviewer.

Ontology validation asks whether a candidate is supported. This asks whether it
is worth asking, which no lookup can decide: triviality, clarity, ambiguity,
difficulty and distractor plausibility are all judgements about a *student*, and
the ontology has no opinion about students.

Everything this module produces is therefore marked `kind="pedagogical"` and
must be reported separately from the deterministic results. It is evidence, not
proof: the reviewer is the same class of model as the generator, and a model
that writes a bad question is not obviously the right judge of one.

The six conditions come from section 10.6 of the work package.

Run it:
    python -m wp4.pedagogical                  review candidates.jsonl in place
    python -m wp4.pedagogical --limit 5        a quick pass
"""

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, Field

from . import generator
from .schemas import STRICT, CandidateRecord, ValidationResult

REVIEW_PROMPT = """You review draft assessment questions for a Python course.

THE LEARNING ITEM THIS QUESTION IS MEANT TO TEST
{item_id}: {title}
{description}

THE QUESTION
Type: {instance_type}
Question: {prompt}
Answer: {answer_key}
{choices}
Judge it against these six conditions. Answer each with true or false, where
true means the condition is satisfied:

targets_the_item   the question tests the learning item above, not some other
                   topic that happens to be related
not_trivial        answering it requires knowing the material, rather than
                   being answerable from the wording alone
wording_is_clear   a student would understand what is being asked
answer_unambiguous exactly one answer is defensible
difficulty_ok      the difficulty suits an introductory course
distractors_ok     for multiple choice only: every wrong choice is plausible
                   but genuinely incorrect. Set true for other question types.

Then give one sentence saying what is weakest about the question.
"""


class PedagogicalReview(BaseModel):
    """The reviewer's structured verdict on one candidate."""

    model_config = STRICT

    targets_the_item: bool
    not_trivial: bool
    wording_is_clear: bool
    answer_unambiguous: bool
    difficulty_ok: bool
    distractors_ok: bool
    comment: str = Field(default="")

    def failures(self) -> list[str]:
        labels = {
            "targets_the_item": "does not target the item",
            "not_trivial": "trivial",
            "wording_is_clear": "wording unclear",
            "answer_unambiguous": "answer ambiguous",
            "difficulty_ok": "difficulty unsuitable",
            "distractors_ok": "a distractor is implausible or also correct",
        }
        return [text for field, text in labels.items() if not getattr(self, field)]


def review(record: CandidateRecord, items: dict, llm=None) -> ValidationResult | None:
    """Judge one candidate. Returns None when there is nothing to judge.

    A candidate that never parsed has no question to review, and asking the
    model to review nothing would manufacture a verdict.
    """
    if record.instance is None:
        return None

    llm = llm if llm is not None else generator.build_model()
    item = items[record.item_id]
    instance = record.instance
    choices = getattr(instance, "choices", None)

    prompt = REVIEW_PROMPT.format(
        item_id=item.id,
        title=item.title,
        description=item.description,
        instance_type=instance.instance_type,
        prompt=instance.prompt,
        answer_key=instance.answer_key,
        choices=f"Choices: {choices}\n" if choices else "",
    )

    try:
        verdict = llm.with_structured_output(PedagogicalReview).invoke(prompt)
    except Exception as error:  # a failed review is not a failed candidate
        return ValidationResult(
            item_id=item.id,
            kind="pedagogical",
            passed=False,
            failures=[f"reviewer produced no verdict: {type(error).__name__}"],
        )

    problems = verdict.failures()
    if problems and verdict.comment:
        problems = problems + [f"reviewer: {verdict.comment}"]

    return ValidationResult(
        item_id=item.id,
        kind="pedagogical",
        passed=not problems,
        failures=problems,
    )


def main() -> None:
    from . import scope_gate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path", type=Path, default=Path(__file__).parent / "candidates.jsonl"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default=generator.MODEL_NAME)
    args = parser.parse_args()

    items = scope_gate.load_items()
    records = [
        CandidateRecord.model_validate_json(line)
        for line in args.path.read_text().splitlines()
        if line.strip()
    ]
    llm = generator.build_model(args.model)

    for number, record in enumerate(records[: args.limit], 1):
        record.pedagogical_validation = review(record, items, llm)
        verdict = record.pedagogical_validation
        state = "n/a" if verdict is None else ("pass" if verdict.passed else "FAIL")
        print(f"[{state}] {number}. {record.item_id} "
              f"{record.generation_input.instance_type}", flush=True)
        if verdict and verdict.failures:
            print(f"      {'; '.join(verdict.failures)[:150]}", flush=True)

    generator.write_records(records, args.path)
    judged = [r for r in records if r.pedagogical_validation]
    passed = sum(1 for r in judged if r.pedagogical_validation.passed)
    print(f"\n{passed}/{len(judged)} passed pedagogical review "
          f"(model judgement, not proof)")
    print(f"written to {args.path}")


if __name__ == "__main__":
    main()
