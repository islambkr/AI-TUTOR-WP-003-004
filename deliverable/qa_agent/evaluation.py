"""evaluation.py -- the evaluation set for AI-TUTOR-WP-003 (acceptance criteria).

32 cases covering every behaviour the work package requires: grounded answers,
identifier citation, refusal, clarification, empty results, and paths.

Every expected value was read from the ontology with graph_service, not from
memory, so a failure means the agent is wrong -- not the expectation.

Run it:
    .venv/bin/python evaluation.py            all cases, writes eval_report.md
    .venv/bin/python evaluation.py refusal    only cases in one category
"""

import sys
import time
from pathlib import Path

from agent import MODEL_NAME, _tool_calls_of, build_agent

# Each case:
#   question  what the student asks
#   category  what behaviour is under test
#   tool      the tool that must be called ("" = any tool, None = no tool at all)
#   expect    every string that must appear in the answer (case-insensitive)
#   forbid    strings that must NOT appear
CASES = [
    # -- definitions, grounded in the ontology's own text ------------------
    dict(id=1, category="definition", question="What is Encapsulation?",
         tool="describe_ontology_entity",
         expect=["bundling data and behaviour", "COOP_ENC"]),
    dict(id=2, category="definition", question="What is Duck Typing?",
         tool="describe_ontology_entity", expect=["COOP019"]),
    dict(id=3, category="definition", question="What is a Metaclass?",
         tool="describe_ontology_entity", expect=["PI_OOP03"]),
    dict(id=4, category="definition", question="What is the Global State Problem?",
         tool="describe_ontology_entity", expect=["DA_OOP07"]),

    # -- dependencies, forward ---------------------------------------------
    dict(id=5, category="dependency", question="What does Encapsulation depend on?",
         tool="find_concept_dependencies", expect=["Class", "COOP001"]),
    dict(id=6, category="dependency", question="What does Abstraction depend on?",
         tool="find_concept_dependencies", expect=["Encapsulation", "COOP_ENC"]),
    dict(id=7, category="dependency", question="What does Duck Typing depend on?",
         tool="find_concept_dependencies",
         expect=["Dunder Method", "Polymorphism"]),
    dict(id=8, category="dependency", question="What does Abstract Class depend on?",
         tool="find_concept_dependencies", expect=["Inheritance", "COOP013"]),
    dict(id=9, category="dependency",
         question="What are all the prerequisites of Data Hiding, including indirect ones?",
         tool="find_concept_dependencies",
         expect=["Encapsulation", "Class"]),

    # -- dependencies, reverse ---------------------------------------------
    dict(id=10, category="dependency-reverse", question="What concepts depend on Class?",
         tool="find_concept_dependencies",
         expect=["Encapsulation", "Inheritance", "Instantiation", "Object"]),
    dict(id=11, category="dependency-reverse", question="What depends on Encapsulation?",
         tool="find_concept_dependencies",
         expect=["Abstraction", "Data Hiding"]),

    # -- named relations ----------------------------------------------------
    dict(id=12, category="relation", question="What contrasts with Inheritance?",
         tool="find_named_relation", expect=["Composition", "Interface"]),
    dict(id=13, category="relation", question="What contrasts with Static Typing?",
         tool="find_named_relation", expect=["Duck Typing", "COOP019"]),
    dict(id=14, category="relation", question="What enables Instantiation?",
         tool="find_named_relation", expect=["Constructor", "OM_OOP01"],
         forbid=["Class"]),
    dict(id=15, category="relation", question="What enables Method Overriding?",
         tool="find_named_relation", expect=["Polymorphism", "COOP018"]),
    dict(id=16, category="relation", question="What type does __repr__ produce?",
         tool="find_named_relation", expect=["str", "DT_OOP_STR"]),
    dict(id=17, category="relation", question="What type does __eq__ produce?",
         tool="find_named_relation", expect=["bool", "DT_OOP_BOOL"]),
    dict(id=18, category="relation", question="What type does __len__ produce?",
         tool="find_named_relation", expect=["int", "DT_OOP_INT"]),
    dict(id=19, category="relation", question="Which error can __repr__ throw?",
         tool="find_named_relation", expect=["TypeError", "E_OOP_TYPE"]),
    dict(id=20, category="relation", question="Which error can __eq__ throw?",
         tool="find_named_relation", expect=["AttributeError", "E_OOP_ATTR"]),
    dict(id=21, category="relation", question="What are the parts of Encapsulation?",
         tool="find_named_relation", expect=["Getter Method", "Setter Method"]),
    dict(id=22, category="relation", question="What is an example of a Dunder Method?",
         tool="", expect=["__repr__"]),  # either relation tool is a valid route

    # -- paths ---------------------------------------------------------------
    dict(id=23, category="path", question="Show a path from Class to Data Hiding.",
         tool="find_relation_path",
         expect=["Encapsulation", "dependsOn"]),
    dict(id=24, category="path", question="How is Object Identity connected to Class?",
         tool="find_relation_path", expect=["Object"]),

    # -- listing --------------------------------------------------------------
    dict(id=25, category="listing", question="Which errors are covered in this lecture?",
         tool="list_lecture_entities", expect=["TypeError", "ValueError"]),
    dict(id=33, category="listing", question="List all the skills taught in this lecture.",
         tool="list_lecture_entities",
         expect=["Applying Inheritance", "Writing Dunder Methods"]),
    dict(id=34, category="listing", question="Which data types are covered?",
         tool="list_lecture_entities", expect=["str", "int", "bool"]),

    # -- refusal: the ontology has no such entity ----------------------------
    dict(id=26, category="refusal", question="What is gradient descent?",
         tool="describe_ontology_entity",
         expect=["no entry", "gradient descent"],
         forbid=["optimization", "optimisation", "loss function", "learning rate"]),
    dict(id=27, category="refusal", question="What is a neural network?",
         tool="describe_ontology_entity", expect=["no entry"],
         forbid=["neuron", "layer", "weights"]),
    dict(id=28, category="refusal", question="What does gradient descent depend on?",
         tool="", expect=["gradient descent"],
         forbid=["derivative", "cost function"]),

    # -- empty result is a real answer, not a failure -------------------------
    dict(id=29, category="empty-result", question="What does __repr__ depend on?",
         tool="find_concept_dependencies",
         expect=["no", "__repr__"],
         forbid=["object", "class definition"]),
    dict(id=30, category="empty-result", question="What contrasts with __repr__?",
         tool="find_named_relation", expect=["no"]),

    # -- ambiguity: must ask back, not guess ----------------------------------
    dict(id=31, category="ambiguity", question="Tell me about abstract.",
         tool="describe_ontology_entity",
         expect=["Abstract Class", "Abstract Method"]),
    dict(id=32, category="ambiguity", question="What does abstract depend on?",
         tool="", expect=["Abstract Class", "Abstract Method"]),
]


def check(case: dict, answer: str, tools_called: list[str]) -> list[str]:
    """Return the reasons this case failed; an empty list means it passed."""
    problems = []
    lowered = answer.casefold()

    wanted_tool = case.get("tool", "")
    if wanted_tool is None:
        if tools_called:
            problems.append(f"called {tools_called}, expected no tool")
    elif wanted_tool == "":
        if not tools_called:
            problems.append("called no tool")
    elif wanted_tool not in tools_called:
        problems.append(f"called {tools_called or 'nothing'}, expected {wanted_tool}")

    for phrase in case.get("expect", []):
        if phrase.casefold() not in lowered:
            problems.append(f"missing {phrase!r}")

    for phrase in case.get("forbid", []):
        if phrase.casefold() in lowered:
            problems.append(f"contains forbidden {phrase!r}")

    return problems


def run(cases: list[dict], model_name: str = MODEL_NAME) -> list[dict]:
    agent = build_agent(model_name=model_name)
    results = []

    for case in cases:
        started = time.time()
        state = agent.invoke({"messages": [{"role": "user", "content": case["question"]}]})
        answer = state["messages"][-1].content or ""
        tools_called = _tool_calls_of(state)
        problems = check(case, answer, tools_called)

        results.append(
            {
                **case,
                "answer": " ".join(answer.split()),
                "tools": tools_called,
                "problems": problems,
                "passed": not problems,
                "seconds": round(time.time() - started, 1),
            }
        )
        mark = "PASS" if not problems else "FAIL"
        print(f"[{mark}] {case['id']:>2}. {case['question'][:58]:<58} {results[-1]['seconds']:>5}s")
        for problem in problems:
            print(f"         {problem}")

    return results


def write_report(results: list[dict], path: Path) -> None:
    passed = sum(1 for r in results if r["passed"])
    by_category: dict[str, list[dict]] = {}
    for result in results:
        by_category.setdefault(result["category"], []).append(result)

    lines = [
        "# Evaluation report -- COMP101 ontology tutor",
        "",
        f"Model: `{MODEL_NAME}`, temperature 0.  ",
        f"Cases: {len(results)}.  Passed: {passed}.  Failed: {len(results) - passed}.",
        "",
        "## By category",
        "",
        "| Category | Passed | Total |",
        "| --- | ---: | ---: |",
    ]
    for category, group in sorted(by_category.items()):
        lines.append(
            f"| {category} | {sum(1 for r in group if r['passed'])} | {len(group)} |"
        )

    failures = [r for r in results if not r["passed"]]
    lines += ["", "## Failures", ""]
    if not failures:
        lines.append("None.")
    for result in failures:
        lines += [
            f"### {result['id']}. {result['question']}",
            "",
            f"- category: {result['category']}",
            f"- tools called: {result['tools'] or 'none'}",
            f"- problems: {'; '.join(result['problems'])}",
            f"- answer: {result['answer']}",
            "",
        ]

    lines += ["## All cases", "", "| # | Category | Question | Tools | Result |",
              "| ---: | --- | --- | --- | --- |"]
    for result in results:
        lines.append(
            f"| {result['id']} | {result['category']} | {result['question']} "
            f"| {', '.join(result['tools']) or '-'} | {'pass' if result['passed'] else 'FAIL'} |"
        )

    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    cases = CASES
    model_name = MODEL_NAME
    args = sys.argv[1:]

    # --model <name> overrides the model, so the same cases can be run against
    # a different Ollama model without editing agent.py.
    if "--model" in args:
        i = args.index("--model")
        model_name = args[i + 1]
        del args[i:i + 2]

    if args:
        wanted = args[0]
        cases = [case for case in CASES if case["category"] == wanted]
        if not cases:
            sys.exit(f"No cases in category {wanted!r}. "
                     f"Available: {sorted({c['category'] for c in CASES})}")

    print(f"model: {model_name}, {len(cases)} cases\n")
    results = run(cases, model_name=model_name)
    passed = sum(1 for r in results if r["passed"])
    print(f"\n{passed}/{len(results)} passed")

    report_path = Path(__file__).with_name("eval_report.md")
    write_report(results, report_path)
    print(f"report written to {report_path.name}")


if __name__ == "__main__":
    main()
