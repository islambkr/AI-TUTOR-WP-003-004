"""generate_set.py -- Step 8 of WP-004: build and store the candidate set.

Five items, three candidates of each type per item: the 45 the work package asks
for in section 5. Every candidate is stored, passing or not, with its generation
input and its rejection reason -- section 10.7 requires that failures stay in
the dataset.

The five items are chosen to keep the distractor comparison possible: three
carry a `contrasts_with` edge and two do not, so MCQ results can be split the
way relation_policy.md section 4 requires.

Run it:
    python -m wp4.generate_set                    writes candidates.jsonl
    python -m wp4.generate_set --n 1              a quick pass, 15 candidates
"""

import argparse
import time
from pathlib import Path

from . import generator, scope_gate

# 3 with a contrasts_with edge, 2 without.
ITEM_IDS = [
    "COMP101-L10-ITEM-004",  # Distinguish instance attributes from class attributes
    "COMP101-L10-ITEM-006",  # Explain encapsulation
    "COMP101-L10-ITEM-008",  # Explain Python name mangling
    "COMP101-L10-ITEM-001",  # Explain what a class represents
    "COMP101-L10-ITEM-003",  # Explain instantiation
]

OUT = Path(__file__).parent / "candidates.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=3, help="candidates per type")
    parser.add_argument("--model", default=generator.MODEL_NAME)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    items = scope_gate.load_items()
    llm = generator.build_model(args.model)
    started = time.time()
    records = []

    for number, item_id in enumerate(ITEM_IDS, 1):
        item = items[item_id]
        print(f"\n[{number}/{len(ITEM_IDS)}] {item}", flush=True)
        for record in generator.generate_for_item(
            item, per_type=args.n, llm=llm, seed=args.seed
        ):
            records.append(record)
            mark = "pass" if record.passed_ontology else "FAIL"
            kind = record.generation_input.instance_type
            print(f"  [{mark}] {kind:<12} {(record.rejection_reason or '')[:80]}",
                  flush=True)

    generator.write_records(records, args.out)
    passed = sum(1 for r in records if r.passed_ontology)
    print(f"\n{passed}/{len(records)} passed ontology validation in "
          f"{time.time() - started:.0f}s")
    print(f"written to {args.out}")


if __name__ == "__main__":
    main()
