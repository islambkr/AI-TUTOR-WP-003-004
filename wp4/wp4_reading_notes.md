# WP-004 reading notes

Islam Bouikiri. Structure fixed by section 4.2 of the work package.

## 1. The difference between an LST item and an instance

An **item** is a type of problem. An **instance** is one concrete case of it.

Doignon and Falmagne make this the first distinction in the theory, and note
that it inverts the psychometric usage: what psychometrics calls an item — a
particular question — is what Knowledge Space Theory calls an instance.

*Explain what a class represents* is an item. It is not something a student can
answer; it names a competence. *Which of the following best describes what a
class represents in Python?*, with four choices, is an instance. A student
answers instances; the assessment infers mastery of the item.

The item file makes this concrete. `COMP101-L10-ITEM-001` carries a title, a
description and a gate. Nothing in it is answerable. The 45 candidates in
`candidates.jsonl` are answerable and none of them is the item.

## 2. Why one item can have many instances

Because an item describes a competence, and a competence can be probed from many
directions. `ITEM-001` allows nine entities and four relation roles; a question
can be built on the definition of Class, on what implements it, on what it has
as parts, or on what enables it, and each can be asked as a short answer, a
true/false statement, or a multiple-choice question.

This is the whole reason the pipeline generates rather than stores. If one item
had one instance, a fixed question bank would do. Because it has many, the
assessment can ask a different instance of the same item on a second attempt,
and two students can be tested on the same competence without being handed the
same question — which is what makes the adaptive procedure of Doignon and
Falmagne section 10 practical.

It also means an instance can be *valid but unrepresentative*: nine instances of
one item may all probe the same corner of it. Coverage across an item is not
guaranteed by grounding, and nothing in this pipeline currently measures it.

## 3. Why ontology grounding does not guarantee pedagogical quality

Grounding answers "is this supported?". Quality answers "is this worth asking?".
They are independent, and the validator tests prove it: two tests assert that a
bad instance **passes** ontology validation.

*Is a Class a class?* is grounded, in scope, correctly cited, and worthless.

*What is a Metaclass?* asked under `ITEM-001` is fully supported — Metaclass is
inside that item's scope — and tests the wrong item.

An MCQ whose distractors are all obviously absurd is grounded and trivially
answerable by elimination.

Grounding is a property of the relationship between the instance and the graph.
Difficulty, clarity, discrimination and item alignment are properties of the
relationship between the instance and a *student*, and the ontology has nothing
to say about students. That is why sections 10.5 and 10.6 are separate steps and
why the report must keep deterministic results apart from model judgements.

## 4. Prompt-only constraints compared with deterministic constraints

A prompt saying "stay inside the ontology" is a request. The model may comply,
and there is no way to know from the output whether it did.

A deterministic constraint is a decision the model cannot reach. `is_entity_allowed`
is set membership; `is_evidence_allowed` is membership of a list built from the
graph. Same input, same answer, every time, with no model in the path.

The sharpest illustration is `is_evidence_allowed`. Consider:

    COOP001 hasPart PI_OOP03

Every part is inside `ITEM-001`'s scope: `COOP001` is allowed, `PI_OOP03` is
allowed, `hasPart` is allowed. A prompt-level instruction — even an allowlist
check on the parts — accepts it. The ontology never asserts it. It is a
fabricated citation, and it is refused only because the check asks whether the
whole triple is in the collected evidence rather than whether its pieces are
permitted.

The honest limit: deterministic constraints only cover what can be looked up.
Whether a distractor is *plausible but incorrect* cannot be decided this way, so
the work package puts it in the model-judgement step instead. Determinism is not
a synonym for correctness — it is a synonym for repeatability.

## 5. How graph relations support different question types

Not all edges carry the same kind of information, so not all edges support the
same kind of question. This is the substance of `relation_policy.md`.

| Relation role | Question it supports |
| --- | --- |
| `definition` | explanation, identification |
| `dependsOn` / `enabledBy` | prerequisite — "what must you know first" |
| `enables` | consequence — "what does this make possible" |
| `contrastsWith` | comparison, discrimination |
| `hasPart` / `partOf` | composition — "what is this made of" |
| `throwsError` | debugging — "which error can this raise" |
| `producesType` / `acceptsType` | output and input prediction |
| `implementedBy` / `usesConcept` | mechanism — "how does this appear in code" |

Two things I only saw by measuring. `definition` supplies 36% of all collected
evidence and is permitted by every one of the 51 items, so a generator sampling
triples uniformly writes mostly explanations; choosing the relation role first
and then a triple within it is what keeps the question types mixed. And an
inverse pair is **one edge for scope but two roles for phrasing** — `hasPart`
and `partOf` are the same fact, yet reading it downward suggests a mechanism
question and upward an identification question.

## 6. How structured output helps validation

Free text has to be interpreted before it can be checked, and interpretation is
where errors enter. A typed schema moves the failure to the boundary.

Concretely, in `schemas.py`:

- `extra="forbid"` — an invented field is malformed output, not something to
  ignore. This is what caught two fields of the item file I had silently
  dropped.
- Three separate variants rather than one class with optional fields — a short
  answer has no `choices` field at all, so it cannot carry choices.
- `answer_key: Literal["true", "false"]` on the true/false variant — a model
  answering "maybe, it depends" has not answered the question, and the schema
  says so rather than a grader discovering it later.
- `choices` distinct and containing the answer, checked by validators.

The practical payoff is that a malformed candidate becomes a *recorded* failure
with a reason attached rather than an exception, which is what section 10.7's
requirement to keep rejects actually needs.

The cost, which I did not anticipate: the schema is only as useful as the model's
ability to fill it. `gemma4:e2b-mlx` could not produce JSON matching any of these
schemas at all.

## 7. Three examples of scope leakage

All three are against `ITEM-001`, whose gate allows `COOP001, LC_OOP_CLASS,
CM_OOP02, CM_OOP05, MR_OOP04, MR_OOP05, OM_OOP01, OM_OOP07, PI_OOP03`.

1. **An out-of-scope concept in the prompt.** *"How does Duck Typing relate to a
   class?"* Duck Typing (`COOP019`) is a true fact of the lecture and is not on
   this item's allowlist. True is not the same as in scope.

2. **An out-of-scope concept in the answer.** *"A Class supports Duck Typing."*
   The prompt is clean and the leak is in the answer key, which is why the
   validator scans both — and, after finding it, the MCQ choices too.

3. **A fabricated citation.** `COOP001 hasPart PI_OOP03` — every part allowed,
   the whole never asserted. This is leakage of a subtler kind: nothing outside
   the scope is named, and the relationship is still invented.

A fourth, which I hit in practice and did not predict: **false leakage**. The
lecture entity `L10` is labelled *"Object-Oriented Programming"*, so a prompt
using that phrase generically was rejected for naming an out-of-scope entity.
The lecture is the container of the material, not a concept inside it.

## 8. Three examples of valid ontology-grounded instances

Generated by the pipeline and passing deterministic validation.

**Short answer, `ITEM-001`:**
> Q: What does a class represent in object-oriented programming?
> A: A class (COOP001) is implemented by a class definition (LC_OOP_CLASS),
> which defines the attributes and methods of objects of that type.

Grounded on `COOP001 implementedBy LC_OOP_CLASS`.

**True/false, `ITEM-001`:**
> A class is a blueprint that defines the attributes and methods all objects of
> that type will have. — **true**

Grounded on `COOP001 definition`. Note the answer carries no ontology content at
all, which is why the validator checks the *statement* for a true/false instance
rather than the answer.

**Multiple choice, `ITEM-001`:**
> Q: Which of the following best describes what a class represents in Python?
> A: A class is a blueprint or template that defines the attributes and methods
> of objects of that type.
> Distractors: a collection of static methods defined with `@staticmethod`; a
> class enabled by a metaclass, which defines its structure; an instance of an
> object that contains attributes.

The distractors are interesting: all three draw on entities inside the item's
scope — Static Method, Metaclass, Object — which is what makes them plausible.
It is also what makes them risky, since an in-scope distractor can turn out to
be correct.

## 9. Open questions for the review meeting

1. **Two item descriptions name an entity their own allowlist excludes.**
   `ITEM-030` names `__init__` (MOOP001), `ITEM-046` names `super()` (FOOP001).
   Descriptions are what the generator writes from, so a faithful question would
   be rejected as out of scope. Should the allowlists gain the entity, or the
   descriptions be reworded?

2. **`gemma4:e2b-mlx` cannot do structured output.** Three prompt formulations
   and `method="json_schema"` all returned plain `key: value` text; the same
   call against `qwen3:latest` parsed first try. WP-003 used gemma4, so the two
   work packages are no longer comparing like with like. Is that acceptable, or
   should WP-003's evaluation be re-run on qwen3?

3. **Runtime.** ~56s per candidate on qwen3, so the full 51 items at nine
   candidates each is about seven hours. The run here is the section 5 minimum
   of five items. Is the full 459 wanted before final submission?

4. **Instance coverage within an item is not measured.** Nine instances of one
   item can all probe the same corner of it. Grounding does not detect this and
   neither does anything else in the pipeline. Should it?

5. **Does the emptiness of `requires` cost anything?** The item file leaves it
   empty deliberately, to test whether generation can do without prerequisite
   information. I saw no case where a candidate failed for lack of it, but I
   also had no way to detect one — I am not sure what evidence would settle this.
