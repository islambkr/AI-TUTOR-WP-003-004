"""evaluate.py -- Step 11 of WP-004: the metrics behind evaluation_report.md.

Reads the stored candidate set and computes the figures the work package asks
for. Deterministic results and model judgements are counted separately and never
combined into one score: one is a lookup and the other is an opinion, and
averaging them would hide which is which.

Run it:
    python -m wp4.evaluate                 print the metrics
    python -m wp4.evaluate --md            emit the report tables as markdown
"""

import argparse
import re
from collections import Counter
from pathlib import Path

from .schemas import CandidateRecord

CANDIDATES = Path(__file__).parent / "candidates.jsonl"


def load(path: Path = CANDIDATES) -> list[CandidateRecord]:
    return [
        CandidateRecord.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def main_reason(record: CandidateRecord) -> str:
    """The single reason a candidate was rejected, for the section 11 breakdown.

    A candidate can fail several checks at once. The first failure is reported
    rather than all of them, because "the main reason" is what the work package
    asks for and a candidate counted under three headings inflates every one.
    """
    if record.instance is None:
        return "malformed output"
    if record.passed_ontology:
        return "none"

    first = (record.ontology_validation.failures or ["unknown"])[0]
    if "out-of-scope entity" in first:
        return "scope violation"
    if "not asserted" in first:
        return "fabricated evidence"
    if "names no entity" in first:
        return "unsupported answer"
    if "item id" in first:
        return "wrong item"
    if "outside the scope" in first:
        return "entity not allowed"
    if "evidence triple" in first:
        return "no evidence cited"
    return "other"


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def near_duplicates(records: list[CandidateRecord]) -> int:
    """Candidates whose prompt repeats one already seen for the same item.

    Compared after lowercasing and stripping punctuation. This catches exact and
    near-exact repeats, not paraphrases -- a paraphrase is a judgement and would
    belong with the model reviewer.
    """
    seen: set = set()
    duplicates = 0
    for record in records:
        if record.instance is None:
            continue
        key = (record.item_id, _normalise(record.instance.prompt))
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates


def rate(count: int, total: int) -> str:
    return f"{count}/{total} ({round(100 * count / total)}%)" if total else "0/0"


def metrics(records: list[CandidateRecord]) -> dict:
    total = len(records)
    parsed = [r for r in records if r.instance is not None]
    passed = [r for r in records if r.passed_ontology]
    reasons = Counter(main_reason(r) for r in records)
    judged = [r for r in records if r.pedagogical_validation]
    accepted = [r for r in records if r.human_decision == "accepted"]

    return {
        "total": total,
        "parsed": len(parsed),
        "ontology_pass": len(passed),
        "scope_violation": reasons["scope violation"],
        "unsupported_answer": reasons["unsupported answer"],
        "fabricated_evidence": reasons["fabricated evidence"],
        "wrong_item": reasons["wrong item"],
        "malformed": reasons["malformed output"],
        "near_duplicates": near_duplicates(records),
        "pedagogical_judged": len(judged),
        "pedagogical_pass": sum(1 for r in judged if r.pedagogical_validation.passed),
        "human_reviewed": sum(1 for r in records if r.human_decision != "unreviewed"),
        "human_accepted": len(accepted),
        "evidence_attached": sum(1 for r in records if r.evidence_attached),
        "reasons": reasons,
    }


def by_type(records: list[CandidateRecord]) -> dict:
    out = {}
    for kind in ("short_answer", "true_false", "mcq"):
        group = [r for r in records if r.generation_input.instance_type == kind]
        out[kind] = (sum(1 for r in group if r.passed_ontology), len(group))
    return out


def mcq_split(records: list[CandidateRecord], items: dict) -> dict:
    """MCQ results split by whether the item carries a contrasts_with edge.

    This is the comparison the mentor asked for: the 16 items with the edge
    against the 35 without, to see what the edge is worth for distractors.
    """
    out = {}
    for label, wants in (("with contrastsWith", True), ("without", False)):
        group = [
            r
            for r in records
            if r.generation_input.instance_type == "mcq"
            and (
                "contrasts_with"
                in items[r.item_id].ontology_gate.allowed_relation_ids
            )
            is wants
        ]
        ungrounded = sum(len(r.ungrounded_distractors) for r in group)
        out[label] = {
            "candidates": len(group),
            "passed": sum(1 for r in group if r.passed_ontology),
            "ungrounded_distractors": ungrounded,
        }
    return out


def main() -> None:
    from . import scope_gate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=CANDIDATES)
    args = parser.parse_args()

    records = load(args.path)
    items = scope_gate.load_items()
    figures = metrics(records)
    total = figures["total"]

    print(f"candidates                {total}")
    print(f"parsed                    {rate(figures['parsed'], total)}")
    print()
    print("-- deterministic --")
    print(f"ontology pass rate        {rate(figures['ontology_pass'], total)}")
    print(f"scope violation rate      {rate(figures['scope_violation'], total)}")
    print(f"unsupported answer rate   {rate(figures['unsupported_answer'], total)}")
    print(f"fabricated evidence rate  {rate(figures['fabricated_evidence'], total)}")
    print(f"item alignment (wrong)    {rate(figures['wrong_item'], total)}")
    print(f"malformed output rate     {rate(figures['malformed'], total)}")
    print(f"near-duplicate rate       {rate(figures['near_duplicates'], total)}")
    print(f"evidence attached by us   {rate(figures['evidence_attached'], total)}")
    print()
    print("-- model judgement --")
    print(f"pedagogical pass rate     "
          f"{rate(figures['pedagogical_pass'], figures['pedagogical_judged'])}")
    print()
    print("-- human --")
    print(f"human acceptance rate     "
          f"{rate(figures['human_accepted'], figures['human_reviewed'])}")
    print()
    print("-- by instance type (ontology) --")
    for kind, (passed, count) in by_type(records).items():
        print(f"{kind:<14} {rate(passed, count)}")
    print()
    print("-- mcq, by contrastsWith --")
    for label, figures_ in mcq_split(records, items).items():
        print(f"{label:<20} passed {rate(figures_['passed'], figures_['candidates'])}"
              f"  ungrounded distractors {figures_['ungrounded_distractors']}")
    print()
    print("-- main rejection reason --")
    for reason, count in figures["reasons"].most_common():
        print(f"{reason:<22} {count}")


if __name__ == "__main__":
    main()
