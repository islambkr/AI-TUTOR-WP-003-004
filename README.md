# AI-TUTOR-WP-003 — Getting Started with Ontologies

An OWL knowledge-graph explorer for `comp101_L10.owl` (COMP101 Lecture 10,
Object-Oriented Programming), plus a LangChain agent that answers questions
using the ontology as its only source of truth.

**Owner:** Islam Bouikiri · **Mentors:** Jalal Maaouni, Asmae Afifi
UM6P Vanguard Center — AI Tutor Engineering Internship

---

## Layout

```
deliverable/
  qa_agent/
    comp101_L10.owl        the ontology (read-only input, never edited)
    inspect_ontology.py    step 2: RDFLib inventory
    queries.sparql         step 3: 10 SPARQL queries
    graph_service.py       step 4: deterministic graph service, no LLM
    tools.py               step 5: LangChain tool wrappers
    prompts.py             the agent's system prompt
    agent.py               the agent (ChatOllama + create_agent), with
                           short-term memory of the current conversation
    evaluation.py          35-case evaluation set
    eval_report.md         results of the most recent evaluation run
    determinism_check.py   proves the service is reproducible across processes
    reasoning_delta.py     reproduces the reasoning figures quoted in the report
    tests/                 107 unit tests, no LLM: the graph service, the
                           SPARQL queries executed against the ontology, the
                           evaluation set checked against raw triples, and how
                           the agent is wired for memory
    requirements.txt
  givenWP/                 the work package and the original ontology
  kg_reading_notes.md      reading artifact
  report.md                engineering report
```

## Architecture

```
comp101_L10.owl       read-only input
  graph_service.py    no LLM, deterministic, returns dicts and lists
    tools.py          thin @tool wrappers, no query logic
      agent.py        the language model
```

The model chooses *which* question to ask the graph and how to word the reply.
It never decides *what* the answer is. Every fact in an answer traces back to a
triple.

## Setup

```bash
cd deliverable/qa_agent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The agent also needs [Ollama](https://ollama.com) running, with the model pulled:

```bash
ollama pull gemma4:e2b-mlx
```

## Running it

```bash
cd deliverable/qa_agent

.venv/bin/python inspect_ontology.py            # ontology inventory
.venv/bin/python -m pytest tests/ -q            # 107 tests, no LLM, ~1s
.venv/bin/python agent.py                       # interactive tutor, follow-ups work
.venv/bin/python agent.py "What is Encapsulation?"
.venv/bin/python determinism_check.py           # same output in 3 processes
.venv/bin/python reasoning_delta.py             # what a reasoner adds
.venv/bin/python evaluation.py                  # 35 cases, writes eval_report.md
```

The SPARQL queries in `queries.sparql` are written to be run in Protégé's SPARQL
tab, or against the graph with RDFLib's `graph.query()`. `tests/test_queries.py`
executes all ten against the ontology on every test run, so a query that stops
returning results fails the suite instead of failing quietly.

## The ontology, measured

| | |
| --- | ---: |
| Asserted triples | 978 |
| Named classes | 16 (+2 anonymous union classes) |
| Named individuals | 66 |
| Object properties | 21 |
| Datatype properties | 5 |

## Notes

The graph service answers from **asserted** triples only — it runs no reasoner.
`TypeProducer` and `ImplementorType` therefore report no individuals, because
their members are inferred through `owl:unionOf`.

This is a deliberate decision, not an omission: asked whether the service should
reason, the mentor's answer was that inference should come from the LLM rather
than from a reasoning engine underneath it. `reasoning_delta.py` stays as a
measurement of what that leaves out — 44 entity-level statements — rather than
as part of the pipeline. See `deliverable/report.md` for the remaining open
questions.