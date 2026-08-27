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
| 3 | `queries.sparql` — 10 SPARQL queries | done, 29 tests execute them |
| 4 | `graph_service.py` — deterministic graph service, 9 functions | done, 74 unit tests |
| 5 | `tools.py`, `prompts.py`, `agent.py` — LangChain agent, 5 tools | done, 4 tests on the memory wiring |
| 6 | `evaluation.py` — 35-case evaluation set | done |

Layering, which is what made the failures below diagnosable:

```
comp101_L10.owl     read-only input, never edited
  graph_service.py  no LLM, deterministic, returns dicts and lists
    tools.py        thin @tool wrappers, no query logic
      agent.py      ChatOllama + create_agent, optional conversation memory
```

The agent was given short-term memory after the work package was written, at the mentor's request. `build_agent` accepts a checkpointer, and `invoke` is passed a thread id naming the conversation; the stored history is then prepended to each new question, so a follow-up can say "it". Asked "What is Encapsulation?" and
then "What does it depend on?" in one thread, the agent answers *Class
(COOP001)*; asked the second question under a different thread id, it correctly asks what "it" refers to.

The interactive tutor runs with memory on: it builds the agent with an
`InMemorySaver` and gives the conversation a thread id. A single question asked
on the command line does not, having nothing to remember, and neither does
`evaluation.py`.

That last one is why the *parameter* defaults to off, and the default is
load-bearing rather than incidental: `evaluation.py` builds one agent and reuses
it for all 35 cases, which are independent by design. Had memory been on by
default, the evaluation would have inherited it silently, every case after the
first would have seen the previous one, and run order would have started to
matter with nothing raised to signal it. `tests/test_agent_memory.py` pins the
default for that reason.

The cost is context. `NUM_CTX` is 8192, the prompt and tool descriptions spend about 1,600 tokens before a question arrives, and each tool result adds roughly 900 more — all of which is re-sent on every remembered turn. A long enough conversation will overflow the window, and section 4.5 records what that looks like: fragments of unrelated answers, silently, with no error. The interactive loop offers `/new` to start a fresh thread; trimming old turns is the real fix
if it becomes a problem in use.

Every failure found by *evaluation* was in the model layer. One defect in the
service itself was found later, by review rather than by testing, and is
recorded in 4.6 — the evaluation could not have caught it, because the
expectations were derived from the same buggy function.

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

35 cases across nine categories: definition, dependency, dependency-reverse,
relation, path, listing, refusal, empty-result, ambiguity.

Expected values were read from the ontology with `graph_service`. That is a
weaker guarantee than it first appears: a bug in the service propagates into
the expectation, which is exactly what happened with the direction defect in
4.6 below — one case asserted the reverse of what the ontology says, and passed.
Every relation case now carries the entity and property it is really asking
about, and `test_evaluation_expectations_match_the_raw_triples` checks those
expectations against the triples directly, bypassing the service.

Results are reported as a range over several runs, not a single figure, because
the agent is not deterministic. The graph service is: the same call produces a
byte-identical result in every process — `determinism_check.py` runs the same
calls in three fresh subprocesses and compares an md5 — and its unit tests
passed unchanged throughout. Only the model layer varies.

Measured over the course of the work, as defects were found and fixed:

| Code version | Cases | Runs | Scores | Spread |
| --- | ---: | ---: | --- | ---: |
| before identifier handling | 34 | 2 | 30, 32 | 2 |
| `citation` on entity records only | 34 | 3 | 26, 27, 28 | 2 |
| identifiers folded into `statement` | 34 | 2 | 32, 14 | **18** |
| context window fixed, payloads trimmed | 34 | 2 | 30, 27 | 3 |
| direction fix, corrected expectations | 35 | 1 | **30** | -- |

Three things this table shows that a single number would hide.

**The spread is itself a measurement.** The 18-point swing in the third row was
not the model being temperamental: it is the signature of the context overflow
diagnosed in 4.5. When the window overflowed, the instructions were truncated
and the answers stopped being near-misses — the agent described the result's
JSON schema instead of the entity, and answered one question with another
question's content. Once the prompt and payloads were trimmed, the spread fell
from 18 points to 5. **Variance narrowed because a bug was fixed, not because
the model changed.**

**The second row is a regression I caused**, not noise. Adding `citation` to
entity records but not to relation records left the prompt relying on a field
that half the results did not carry.

**The remaining variance is real and will not go away.** Individual failures
recur in no fixed pattern: across runs the agent has passed `label_or_id="__"`,
truncating a dunder name, and has answered a question about Encapsulation with
facts about Dunder Method. No case fails consistently, and nothing in the
service explains either failure. Tool choice and argument extraction are not
deterministic even at temperature 0, while the service beneath them is.

The last row is the only one measured against the corrected set, and it is a
single run, so it is a data point rather than a rate. Every earlier row was
scored against one reversed expectation that the buggy code satisfied, which is
why they are kept only to show the shape of the variance, not as results.
`eval_report.md` is the committed report for that run.

**The five failures in the 30/35 run are all about identifiers or arguments,
not about facts.** Cases 1 and 2 gave correct, well-grounded definitions but
omitted the identifier. Case 24 was worse: it reported "Object (COOP_OBJ_ID)"
when Object is COOP002 — reusing the neighbouring entity's identifier rather
than omitting one. Cases 20 and 21 failed on arguments: one call passed
`label_or_id="__"`, truncating a dunder name, and one asked for a relation the
tool then reported as absent, though the service returns it correctly when
called directly.

Nothing in the ontology or the service produced a wrong fact in this run. Every
failure was the model mishandling an identifier or an argument, which is what
the layering predicts and what makes the failures cheap to diagnose.

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
evaluation cases — answers to earlier questions appearing in later ones. It was
not: building a fresh agent for each question, in a separate ad-hoc script,
reproduced the same wrong arguments. (`evaluation.py` itself reuses one agent,
which is harmless because `create_agent` keeps no state between invocations
without a checkpointer.) The model was copying sample values instead of reading
the question.

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

### 4.6 A relation and its inverse answered the same question

Found in review, after the evaluation runs reported above.

`get_relations_by_name` accepted the requested property *or* its
`owl:inverseOf` partner, then filtered records that `_relations_of` had already
collapsed to one direction. The effect: asking for `hasPart` returned `partOf`
facts, and `enables` returned `enabledBy` facts.

```
get_relations_by_name("Getter Method", "hasPart")
  -> "Getter Method (MR_OOP01) partOf Encapsulation (COOP_ENC)"
```

The statement itself was never false — it was the answer to the opposite
question. Across the ontology, 348 of 696 returned records used the inverse of
the property requested.

The fix queries the graph in the requested orientation rather than filtering
collapsed records: `X hasPart ?y` is satisfied by an asserted `X hasPart ?y`
or by `?y partOf X`, but never by `X partOf ?y`. After it, 0 of 370 records use
a predicate other than the one asked for, checked exhaustively by a test.

**This defect had been written into the evaluation set.** Case 15 asked "What
enables Method Overriding?" and expected Polymorphism, but the ontology asserts
the reverse -- Method Overriding *enables* Polymorphism, and nothing enables
it. The expectation came from `graph_service`, so the bug validated itself. The
case now tests the asserted direction, and a new case checks that the opposite
direction correctly returns nothing.

That is the sharpest lesson of the project: **an expectation derived from the
code under test cannot detect a bug in that code.** Each relation case now
declares the entity and property it asks about, and a test verifies its expected
answer against the raw triples rather than against `graph_service`.

## 5. Open questions

1. **Should the graph service use a reasoner?** — *decided: no.*
   Right now it only reads facts that are written in the file. Some facts are
   not written but follow logically — for example every Method is also a
   TypeProducer. Because I do not run a reasoner, asking "which entities are
   TypeProducers?" returns nothing.

   Asked directly, the mentor's answer was that the inference should come from
   the LLM rather than from a reasoning engine in the service — that is where
   the value of using an agent lies. So the graph service stays on asserted
   triples, and `reasoning_delta.py` remains a measurement of what is being left
   out (44 entity-level statements), not a component of the pipeline.

   The gap this leaves is unchanged and still worth stating: a student asking
   "which entities are TypeProducers?" gets an empty answer, which reads as
   "there are none" rather than "none are written down". Whether the model closes
   that gap reliably has not been measured, and no case in the 35 tests for it.

2. **How should the agent's score be reported?**
   The graph service gives the same answer every time. The agent does not: the
   same code scored between 14 and 32 out of 34 on different runs. I report a
   range. Is a range acceptable, or is a single number expected?

3. **Was it right to ignore the `teaches` relation when finding paths?**
   The lecture is linked to all 65 other entities, so any two entities are always two
   steps apart through the lecture. That path is true but tells the student
   nothing, so I excluded it and show concept-to-concept paths instead. That was
   my judgement, not a rule from the ontology.

4. **Should the ontology keep writing both directions of every relation?**
   The file states both "A teaches B" and "B taughtIn A". A reasoner could
   derive the second from the first. Keeping both means the file works without a
   reasoner, but every manual edit has to be made twice.

## 6. Known gaps

* The test suite covers `graph_service.py`, the SPARQL queries, the evaluation
  set itself, and how `agent.py` is wired for memory. `tools.py` and
  `prompts.py` still have no tests, and `tools.py` was substantially rewritten
  late in the work with only evaluation runs as verification.
* **Conversation memory is tested as wiring, not as behaviour.** The four tests
  in `tests/test_agent_memory.py` check that the default is memoryless, that a
  checkpointer is attached when given, and that a thread id is mandatory. That
  the model actually *uses* the remembered turns was confirmed by hand, on the
  "What is Encapsulation?" / "What does it depend on?" exchange quoted in
  section 1, and is not covered by any automated case. It belongs in
  `evaluation.py`, which was left unchanged so that the runs of the 35-case set
  still needed for a rate stay comparable with the committed 30/35.
* **One run is not a rate.** The corrected 35-case set has been run once, at
  30/35, and that report is committed. At least two more runs are needed before
  a figure is quoted, given the spread seen on earlier versions.
* **Identifier citation is the weakest behaviour.** Three of the five failures in
  that run were identifiers omitted or, in one case, a neighbouring entity's
  identifier reused. The facts were right; the citation was not. The remaining
  two were substantively wrong: case 20 passed `"__"` as the entity and got an
  ambiguity response instead of an answer, and case 21 reported no parts for
  Encapsulation when two are asserted.
* **Grounding and citation are scored as one number.** The acceptance criteria
  list them separately — the agent must call a tool before a factual answer, and
  must include an entity identifier — but `check()` fails a case for either. So
  the criterion the agent meets reliably and the one it does not are averaged
  together, and the weaker behaviour is not visible per run.
* The relation-direction defect in 4.6 was found by review, not by the test
  suite. Relation cases now declare their ground truth and are checked against
  the raw triples, so the same class of defect would fail a test.
* `gemma4:e2b-mlx` mishandles underscore-heavy identifiers: `__len__` questions
  were observed answered about `__repr__`, and one tool call passed
  `label_or_id="__"`. Normal labels are reliable. This was observed before the
  context fix and has not been re-measured since; it may have been another
  symptom of truncation rather than a tokenisation weakness.

## 7. How to run

```bash
cd deliverable/qa_agent
.venv/bin/python -m pytest tests/ -v      # 107 unit tests, no LLM, ~1s
.venv/bin/python determinism_check.py     # same results across 3 processes
.venv/bin/python reasoning_delta.py       # reproduces the reasoning figures
.venv/bin/python evaluation.py            # 35 agent cases, writes eval_report.md
.venv/bin/python agent.py                 # interactive tutor, remembers the thread
.venv/bin/python agent.py "What is Encapsulation?"
```

Ollama must be running with `gemma4:e2b-mlx` pulled.