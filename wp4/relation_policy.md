# Relation policy — WP-004 §7

Which ontology relations may support an instance, and what kind of instance each
one supports. The work package is explicit that edges are not interchangeable:
"Do not treat all edges as equivalent." This file records the choice made for
each relation and why.

The scope gate enforces the allowlist mechanically. It does not know what a
relation *means*, so nothing here is checked by `scope_gate.py`; this is the
reasoning behind the allowlists the item file ships, and the input to
pedagogical validation in §10.6.

## 1. The relations actually in use

Ten inverse pairs plus `definition` and the symmetric `contrastsWith`, across
the 51 items. Counts are measured after the inverse expansion of §1.1: `items`
is how many item gates permit the relation, `evidence` is how many triples the
gate collects for it across all items.

| Relation | Items | Evidence | Role | Instance use |
| --- | ---: | ---: | --- | --- |
| `definition` | 51 | 204 | Definition | Explanation, identification |
| `contrastsWith` | 16 | 52 | Contrast | Comparison |
| `usesConcept` / `isUsedBy` | 23 | 40 / 40 | Mechanism | Mechanism, example |
| `enables` / `enabledBy` | 17 | 26 / 26 | Dependency | Consequence, prerequisite |
| `hasPart` / `partOf` | 13 | 25 / 25 | Composition | Mechanism, identification |
| `dependsOn` / `isRequiredBy` | 16 | 21 / 21 | Dependency | Prerequisite |
| `throwsError` / `isThrownBy` | 14 | 19 / 19 | Error | Debugging |
| `hasExample` / `exampleOf` | 10 | 13 / 13 | Example | Identification |
| `producesType` / `isProducedBy` | 6 | 6 / 6 | Output | Output prediction |
| `implementedBy` / `implements` | 3 | 5 / 5 | Implementation | Mechanism |
| `acceptsType` / `isAcceptedBy` | 1 | 1 / 1 | Input | Input prediction |

**568 triples in total.** An item permits between 2 and 6 relations as written
in the file: median 3, mean 3.35, mode 4. The distribution is flat rather than
peaked — 14 items allow two, 14 allow three, 15 allow four — so no single count
is "typical".

### 1.1 An allowed relation implies its inverse

Mentor decision: *for a given relation, assume its opposite as well.* An item
permitting `is_used_by` therefore also permits `usesConcept`.
`scope_gate.with_inverses` applies this from the ontology's own `owl:inverseOf`
assertions.

**This does not widen the gate.** Entities stay on the allowlist, the pairs are
asserted in the file rather than guessed, and the expansion is a dictionary
lookup — assuming the opposite is not traversing another hop. `contrastsWith`
gains nothing, being `owl:SymmetricProperty` rather than half of a pair, and
`teaches`/`taughtIn` stay unreachable because no item allows either and adding
the partner of an absent relation adds nothing. Three tests hold those three
claims.

What it changed, measured:

| | Before | After |
| --- | ---: | ---: |
| Evidence triples | 413 | **568** (+38%) |
| Items declaring an uncollected triple | 5 | **0** |
| `definition`'s share of evidence | 49% | **36%** |
| Redundant direction spellings | — | 182 (32%) |

## 2. Each relation, and why it is allowed

**Which layer each claim below belongs to.** This section argues that direction
carries pedagogical weight — `has_part` reads downward for a mechanism question,
`part_of` upward for identification. §1.1 says the two are one edge. Both hold,
because they are about different layers: **an inverse pair is one edge for
scope, two roles for phrasing.** The gate decides what a question may draw on,
and there the pair is a single fact; the generator decides how to ask, and there
the direction chosen changes the question. Nothing else collapses — WP §7's "do
not treat all edges as equivalent" is untouched, since only inverse pairs merge
and only for scope.

**`definition` — explanation and identification.** The datatype property carrying
the entity's own text. It supports "explain X" and "which of these describes X",
and it is the only relation that can ground an instance about a single entity
with no neighbour. Allowed for every item.

**`contrasts_with` — comparison, and the candidate distractor source.**
*Instance Attribute (CM_OOP01) contrastsWith Class Attribute (CM_OOP02).* The
ontology asserts that two entities are opposed, which is exactly what a
discrimination question needs. Whether that also makes it a better distractor
source than an unaided model is no longer assumed here — it is the experiment
§4 describes, measured across the 16 items that carry the edge and the 35 that
do not.

**`depends_on`, `enabled_by`, `is_required_by` — prerequisite questions.**
*Object (COOP002) dependsOn Class (COOP001).* These carry the learning order, so
they support "what must you understand before X". They are the closest thing in
the ontology to a surmise relation, but they are **not** the same thing, and the
item file says so: `lst_requires_policy` forbids converting `depends_on` edges
into LST prerequisites. Every item ships `requires: []`, and that is not a gap
awaiting authoring: the mentor's answer is that the emptiness is the experiment,
"to assess if instance generation can do without that information". The
evaluation report therefore owes an observation on whether generation suffered
for the lack of it.

**`enables` — consequence.** *Self Reference (OM_OOP02) enables Instance
Attribute (CM_OOP01).* The reverse reading of a dependency: not "what does X
need" but "what does X make possible". Worth separating from `depends_on`
because the question it produces is different, and because WP-003 recorded a
defect where the two directions were answered interchangeably.

**`throws_error` — debugging.** *`__init__` (MOOP001) throwsError TypeError
(E_OOP_TYPE).* Supports "which error can X raise", the only relation that
grounds a diagnostic question rather than a descriptive one.

**`produces_type`, `accepts_type` — output and input prediction.**
*`isinstance()` (FOOP002) producesType bool (DT_OOP_BOOL).* Narrow, factual, and
unambiguous, which makes them the safest ground for a true/false instance.

**`has_part`, `part_of` — composition.** *Class (COOP001) hasPart Dunder Method
(OM_OOP07).* Supports "what does X consist of". The direction matters: `has_part`
reads downward for a mechanism question, `part_of` upward for identification.

**`has_example`, `example_of` — identification.** *`__init__` (MOOP001) exampleOf
Constructor (OM_OOP01).* Grounds "give an example of X", where the answer is
fixed by the ontology instead of invented.

**`implemented_by`, `is_used_by` — mechanism.** *Class (COOP001) implementedBy
class definition (LC_OOP_CLASS).* How a concept appears in real Python, which
supports a mechanism question without becoming a code-writing task — WP-004
excludes code questions.

**`uses_concept` — mechanism and example.** *Instance Attribute (CM_OOP01)
usesConcept `__dict__` (PI_OOP04).* The broadest of the allowed relations, and
the one to treat with most care: it says two things are related without saying
how, so an instance built on it alone risks being vague.

## 3. What is excluded, and why

**`teaches` / `taught_in`.** Excluded by the item file, and
`test_lecture_membership_edges_are_never_evidence` proves no item can reach them.
Every entity is connected to the lecture, so these edges make any two entities
two steps apart. The connection is true and carries no information at item level.
WP-003 reached the same conclusion independently and excluded them from path
finding (report §5, open question 3).

**Nothing else is excluded — and duplication is now a sampling problem.** Where
a relation has an `owl:inverseOf`, the ontology asserts both directions, so
about 185 of its 978 triples restate a fact already present. Since §1.1 makes an
allowed relation imply its inverse, both spellings now reach the evidence:

| Source of the redundant half | Triples |
| --- | ---: |
| `owl:inverseOf` pairs | 156 |
| `contrastsWith`, symmetric and asserted both ways | 26 |
| **Total, of 568** | **182 (32%)** |

At 32% this is no longer a footnote about §11's near-duplicate metric. A
generator sampling evidence uniformly draws the same fact twice about a third of
the time, and would produce visibly repetitive candidates. **Canonicalise
direction when sampling — pick one spelling per underlying edge — and keep both
available for phrasing**, which is the §2 distinction applied.

## 4. Two consequences for generation

**`definition` dominates, and that is a diversity problem.** It supplies 204 of
the 568 collected triples — 36% of all evidence, and it is permitted by all 51
items. A generator sampling evidence uniformly will produce mostly explanation
instances, and the required mix of short-answer, true/false and MCQ will come
out lopsided.

Mentor decision: weigh it down. The mechanism is to **choose the relation role
first, then a triple within it**, rather than sampling triples directly. Note
that the inverse expansion already did part of the work on its own, taking
`definition` from 49% to 36% by enlarging everything else.

The same treatment probably belongs on `usesConcept`/`isUsedBy`, which after the
merge is 80 triples — 14% of all evidence and the largest block after
`definition`. §2 warns that this pair says two things are related without saying
how, so it is simultaneously the most plentiful evidence and the vaguest.

**Distractors are the hard part, and only 16 items have a safe source.** An MCQ
distractor must be plausible and wrong. The obvious approach — pick another
entity from the item's allowlist — is unsafe, because the allowlist is built from
entities *related* to the anchor, so a distractor drawn from it may well also be
correct. Encapsulation's scope contains both Getter Method and Setter Method, and
both are genuinely its parts, so either is a false distractor for "what is part
of Encapsulation".

`contrastsWith` is the only relation that asserts opposition, which makes its
neighbours plausible and wrong by construction. Only 16 of 51 items permit it.

**Mentor decision: let the model write the distractors, then measure whether
that edge mattered.** The 16 items carrying `contrastsWith` are compared against
the 35 without, and the difference is the evidence for how much the edge is
worth. That makes this an experiment rather than an open question, and it
constrains the validator: a deterministic rule requiring every distractor to
name an in-scope entity would give those 35 items a near-zero MCQ pass rate *by
construction*, and the comparison would measure the rule instead of the
ontology. So `_answer_is_supported` requires only the **answer** to be grounded.

What stays deterministic on a choice is leakage — a distractor naming an
out-of-scope entity is still refused, because that is a lookup rather than an
opinion. A distractor naming no ontology entity at all is counted by
`validator.ungrounded_distractors` as a signal for §11, not a rejection.
Plausibility remains a judgement, which is where WP §10.6 puts it.

**This adds a requirement to the evaluation report:** MCQ metrics must be
reported separately for the 16 `contrastsWith` items and the 35 without.
Aggregated, the comparison the mentor asked for is invisible.

## 5. Two decisions recorded, not inferred

**Input models reject unknown fields.** `Item` and `OntologyGate` are
`extra="forbid"`, so a field added to the item file breaks the loader until it
is modelled. That is deliberate, and it is not free: a mentor adding one key has
to touch `schemas.py` too. The alternative was worse. The first version of these
models silently dropped `evidence_triples` and `grounding_status` because
Pydantic ignores unknown keys by default, and every test passed while two fields
went unread — which is how the direction finding in §6 stayed invisible.

**Stored records do not all carry the same field names.** The work package's §9
says "use the same field names for all generated records", and after splitting
`CandidateInstance` into three variants a stored short-answer record has no
`choices` key at all rather than `choices: null`. The reason to deviate is that
the split is what makes the per-type rules enforceable by the schema instead of
by a validator: a short answer cannot hold choices, a true/false answer can only
be `true` or `false`, and an MCQ's choices must be distinct and contain the
answer. Reading is unaffected — the discriminated union parses all three. If the
mentor prefers uniform keys on disk, the fix is to serialise with the absent
fields filled as null rather than to merge the models back together.

A related note for step 10.4: the union compiles to a JSON schema using `oneOf`
plus a discriminator, and small local models fill branching schemas unreliably.
The generator should therefore hand the model the concrete variant for the type
it asked for — `INSTANCE_MODELS[requested_type]` — and keep the union for
parsing stored records.

## 6. Decisions from the review

Five questions were put to the mentor. Four are answered and implemented; the
fifth was raised by this document and is still open.

**1. The snake_case / camelCase mismatch — decided: map it.** *"Feel free to map
them if necessary."* The item file writes `depends_on`, the ontology declares
`dependsOn`, and all sixteen relation ids differ this way.
`scope_gate.to_owl_property` translates and a test pins the mapping, so the item
file is left as the mentor wrote it. Closed.

**2. Should an allowed relation imply its inverse — decided: yes.** *"For a
given relation assume its opposite as well."* Implemented in
`scope_gate.with_inverses`; see §1.1 for what it changed and §2 for why one edge
for scope is still two roles for phrasing. This dissolved the finding that
prompted the question: five items had declared a triple in the direction
opposite to their own allowlist, and now none do. `compare_declared_evidence` is
kept, because it still catches a file citing something asserted in neither
direction. Closed.

**3. Two item descriptions name an entity their own allowlist excludes — still
open.** ITEM-030's description names `__init__` (MOOP001) and ITEM-046's names
`super()` (FOOP001). These are entity questions, so the inverse decision does
not touch them. They are the only two of the 51 that leak, and descriptions are
what the generator writes questions from, so a question faithful to either
description would be rejected as out of scope. Should the allowlists gain the
entity, or the descriptions be reworded?

**4. Should `definition` be weighted down — decided: yes.** Sampling picks the
relation role first and then a triple within it, rather than sampling triples
directly. The inverse expansion already took `definition` from 49% to 36% on its
own. `usesConcept`/`isUsedBy` is the next candidate for the same treatment, at
80 triples and 14%. Closed.

**5. Distractors for the 35 items without `contrasts_with` — decided: let the
model write them, and measure.** *"Rely on the LLM to generate distractors, then
compare results with items that have `contrasts_with` relations to assess the
importance of said edges."* This is now an evaluation requirement rather than an
open question: MCQ metrics are reported separately for the 16 and the 35. See §4
for what it removed from the validator. Closed.

**6. `requires` stays empty on purpose.** *"To assess if instance generation can
do without that information."* The emptiness is the experiment, not a gap
awaiting authoring — so the evaluation report owes an observation on whether
generation suffered for the lack of prerequisite information. The item file's
`lst_requires_policy` already forbids deriving it from `depends_on`, and this
confirms why.

## 7. What the generation run and the report must do

Written before generation starts, because two of these are decisions the run
cannot be re-made without repeating it.

**Volume.** WP §8 requires three short-answer, three true/false and three MCQ
per item. Across all 51 items that is **459 candidates**, not the 45 the work
package's own arithmetic mentions — 45 is the figure for the five-item minimum
of §5. The item file supplies 51 mentor-approved items, so 459 is the number
unless the mentor prefers to scope the run to five.

**The distractor experiment.** MCQ metrics reported separately for the 16 items
carrying `contrastsWith` and the 35 without. Aggregated, the comparison the
mentor asked for is invisible. `validator.ungrounded_distractors` supplies the
per-candidate signal.

**Sampling.** Choose the relation role first, then a triple within it, and
canonicalise direction so an edge is not drawn twice under two spellings — §3
and §4.

**Prerequisites.** An observation on whether generation suffered from
`requires` being empty, per §6 question 6.

**Provenance.** WP §10.7 requires each stored candidate to carry its generation
input, the instance, the ontology verdict, the pedagogical verdict, the human
decision and the rejection reason. That record model does not exist yet; it is
the next schema to write, and the ungrounded-distractor signal belongs on it
rather than inside `ValidationResult`.
