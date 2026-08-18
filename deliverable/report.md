# AI-TUTOR-WP-003 — Engineering report

**Owner:** Islam Bouikiri · **Mentors:** Jalal Maaouni, Asmae Afifi
**Ontology:** `comp101_L10.owl` (COMP101 Lecture 10, Object-Oriented Programming)
**Model:** `gemma4:e2b-mlx` via Ollama, temperature 0

---

## 1. What was built

| Step | Artifact | State |
| --- | --- | --- |
| 1 | Ontology inspected in Protégé, HermiT reasoner run | done |
| 2 | `inspect_ontology.py` — RDFLib inventory | done |
| 3 | `queries.sparql` — 10 SPARQL queries | done |
| 4 | `graph_service.py` — deterministic graph service, 8 functions | done, 68 unit tests |
| 5 | `tools.py`, `prompts.py`, `agent.py` — LangChain agent, 5 tools | done |
| 6 | `evaluation.py` — 34-case evaluation set | done |

Layering, which is what made the failures below diagnosable:

```
comp101_L10.owl     read-only input, never edited
  graph_service.py  no LLM, deterministic, returns dicts and lists
    tools.py        thin @tool wrappers, no query logic
      agent.py      ChatOllama + create_agent
```

Every failure encountered during evaluation was in the model layer. The graph
service never produced a wrong fact, and its 68 tests passed unchanged
throughout.

## 2. The ontology as measured

| Property | Value |
| --- | ---: |
| Asserted triples | 978 |
| Named classes | 16 (+2 anonymous `owl:unionOf` expressions) |
| Named individuals | 66 |
| Object properties | 21 |
| Datatype properties | 5 |
| Distinct relation facts after collapsing inverses | 185 |

Two findings worth stating:

**Every inverse pair is asserted twice.** The file states both `teaches` and
`taughtIn`, both `producesType` and `isProducedBy`, and so on. Roughly 185 of
the 978 triples are the second half of a pair a reasoner would infer for free.
The graph service collapses them so a fact is reported once; a test verifies
that no neighbour is lost for any of the 66 individuals.

**Reasoning adds 44 statements about entities.** Running OWL-RL over the file
adds 27 `rdf:type` assertions (from the `owl:unionOf` equivalences), 7
`rdfs:subClassOf` edges, and 5+5 `dependsOn`/`isRequiredBy` links from
transitivity. Notably, `partOf` is declared transitive but yields nothing: all
13 of its assertions are single hops with no chains to close.

## 3. Evaluation

34 cases across eight categories: definition, dependency, dependency-reverse,
relation, path, listing, refusal, empty-result, ambiguity.

Expected values were read from the ontology with `graph_service`, never from
memory, so a failing case means the agent is wrong rather than the expectation.

Results are reported as a range over several runs, not a single figure, because
the agent is not deterministic. The graph service is: the same call produces a
byte-identical result in every process (verified by comparing an md5 of the
JSON output across three runs), and its 68 unit tests passed unchanged
throughout. Only the model layer varies.

Measured over the course of the work, as defects were found and fixed:

| Code version | Runs | Score (of 34) |
| --- | --- | --- |
| before identifier handling | 2 | 30, 32 |
| `citation` added to entity records only | 3 | 26, 27, 28 |
| identifiers folded into `statement` | 2 | 32, 14 |
| context window fixed, payloads trimmed | 2 | 30, 27 |

Two things this table shows more clearly than any single number would.

**The 14/34 run matters more than the 32.** It came from the same code, minutes
after, and its failures were not near-misses: the agent described the JSON
schema instead of the entity, and answered one question with another question's
content. That is the signature of context overflow, diagnosed in 4.5 below.

**The middle row is a regression I caused**, not noise. Adding `citation` to
entity records but not to relation records left the prompt telling the model to
rely on a field that half the results did not carry.

The final configuration has not been measured over enough runs to quote a
stable figure. Two runs gave 30 and 27; the three runs intended to confirm the
last prompt fixes were interrupted. This should be re-run before any pass rate
is quoted.

## 4. Failures and how they were fixed

Five defects were found by evaluation. All were in the model layer, and in
every case the working fix was to move correctness into the tool output
rather than to add another instruction to the prompt.

### 4.1 Relation direction reported backwards

The agent stated *"Class depends on Encapsulation"* when the ontology asserts
the reverse. Relation records carried `from`, `to` and `direction`, and the
model read them left to right, ignoring `direction: incoming`.

Adding a `statement` field, precomputed in subject-predicate-object order
(`"Encapsulation dependsOn Class"`), fixed it. A prompt instruction to respect
the `direction` field had not.

### 4.2 Wrong tool for named relations

Asked *"What enables Instantiation?"*, the agent called the dependency tool and
answered with `dependsOn` — reporting Class, which does not enable
Instantiation. Measured over four runs at temperature 0, it chose the right
tool twice and the wrong tool twice: **tool selection is not deterministic even
at temperature 0**, though the graph service is.

An explicit prompt rule not to use the dependency tool did not fix it. Adding
`find_named_relation`, a tool that exactly fits the question, did: 5 of 5
subsequent runs correct. Making the right action easy worked where forbidding
the wrong one failed.

### 4.3 Tool arguments copied from docstring examples

The most instructive failure. Asked *"What type does `__len__` produce?"*, the
agent called:

```python
find_named_relation(label_or_id='__repr__', relation='throwsError')
```

Both arguments are wrong, and both appear as **examples in the tool
docstrings**. The symptom looked like conversation state leaking between
evaluation cases — answers to earlier questions appearing in later ones — but a
fresh agent per case reproduced it. The model was copying sample values instead
of reading the question.

The same root cause had produced an earlier symptom: the system prompt
illustrated rule 5 with `"Encapsulation (COOP_ENC)"`, and the agent then
stamped `COOP_ENC` onto unrelated entities, including invented hybrids like
`COOP_ENC_COOP001`.

Replacing every concrete example in prompts and docstrings with placeholders
fixed both. **Concrete examples in tool descriptions are copied verbatim as
arguments by a small model.**

### 4.4 Identifiers omitted from answers

Acceptance requires an identifier in every factual answer. Rule 5 asked for it;
compliance was inconsistent, especially on prose-heavy definition answers.

Adding a `citation` field (`"Encapsulation (COOP_ENC)"`) to every record and
instructing the model to copy it verbatim raised the definition category from
1/4 to 4/4.

This fix initially regressed the relation category, because `citation` was
added only to entity records — relation records had none, so the model had
nothing to copy and omitted identifiers entirely. Adding `citation` to relation
records and path steps resolved it. The lesson: when the prompt is told to rely
on a field, every record type must carry it.

### 4.5 The context window was overflowing

The largest defect, and the one that had been misread as model weakness.

Ollama defaults to a 4096-token context. The system prompt and the five tool
schemas cost roughly 2,700 tokens before the question was asked, and a single
`describe_entity` result added about 900 more. Ordinary exchanges therefore
exceeded the window, and the instructions were truncated away.

Every symptom that had looked like a small model failing to cope followed from
that: describing the result's JSON schema instead of the entity, answering one
evaluation case with another case's content, and calling a tool with a
truncated argument (`label_or_id="__"`).

Three changes, none of which required a larger model:

| | before | after |
| --- | ---: | ---: |
| system prompt | 723 tokens | 367 |
| five tool schemas | 1,985 tokens | 1,243 |
| one `describe_entity` result | 917 tokens | 247 |
| context window | 4,096 (default) | 8,192 (explicit) |

The payload reduction was pure redundancy: each relation record repeated the
same entity across `iri`, `id`, `label`, `citation` and `statement`, when
`statement` already contains both names and both identifiers. The tool layer now
forwards only the sentences. The graph service still returns the full record the
work package requires, and its tests were unaffected.

Answer latency also fell from 8-18 seconds per question to 2-7.

## 5. Open questions

1. **Should the graph service use a reasoner?**
   Right now it only reads facts that are written in the file. Some facts are
   not written but follow logically — for example every Method is also a
   TypeProducer. Because I do not run a reasoner, asking "which entities are
   TypeProducers?" returns nothing. Should the tutor teach what is written, or
   also what follows from it?

2. **How should the agent's score be reported?**
   The graph service gives the same answer every time. The agent does not: the
   same code scored between 14 and 32 out of 34 on different runs. I report a
   range. Is a range acceptable, or is a single number expected?

3. **Was it right to ignore the `teaches` relation when finding paths?**
   The lecture is linked to all 66 entities, so any two entities are always two
   steps apart through the lecture. That path is true but tells the student
   nothing, so I excluded it and show concept-to-concept paths instead. That was
   my judgement, not a rule from the ontology.

4. **Should the ontology keep writing both directions of every relation?**
   The file states both "A teaches B" and "B taughtIn A". A reasoner could
   derive the second from the first. Keeping both means the file works without a
   reasoner, but every manual edit has to be made twice.

## 6. Known gaps

* Only `graph_service.py` has unit tests. `tools.py`, `prompts.py` and
  `agent.py` have none, and `tools.py` was substantially rewritten late in the
  work with only evaluation runs as verification.
* The final configuration needs three clean evaluation runs before a pass rate
  is quoted.
* `gemma4:e2b-mlx` mishandles underscore-heavy identifiers: `__len__` questions
  were observed answered about `__repr__`, and one tool call passed
  `label_or_id="__"`. Normal labels are reliable. This was observed before the
  context fix and has not been re-measured since; it may have been another
  symptom of truncation rather than a tokenisation weakness.

## 7. How to run

```bash
cd "deliverable/Q&A agent"
.venv/bin/python -m pytest tests/ -v      # 68 unit tests, no LLM, ~0.2s
.venv/bin/python evaluation.py            # 34 agent cases, writes eval_report.md
.venv/bin/python agent.py                 # interactive tutor
.venv/bin/python agent.py "What is Encapsulation?"
```

Ollama must be running with `gemma4:e2b-mlx` pulled.
