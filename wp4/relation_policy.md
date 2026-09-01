# Relation policy — WP-004 §7

Which ontology relations may support an instance, and what kind of instance each
one supports. The work package is explicit that edges are not interchangeable:
"Do not treat all edges as equivalent." This file records the choice made for
each relation and why.

The scope gate enforces the allowlist mechanically. It does not know what a
relation *means*, so nothing here is checked by `scope_gate.py`; this is the
reasoning behind the allowlists the item file ships, and the input to
pedagogical validation in §10.7.

## 1. The relations actually in use

Sixteen distinct relations appear across the 51 items. Counts are measured, not
estimated: `items` is how many item gates permit the relation, `evidence` is how
many triples the gate collects for it across all items.

| Relation | Items | Evidence | Role | Instance use |
| --- | ---: | ---: | --- | --- |
| `definition` | 51 | 204 | Definition | Explanation, identification |
| `contrasts_with` | 16 | 52 | Contrast | Comparison; distractors |
| `uses_concept` | 20 | 36 | Mechanism | Mechanism, example |
| `depends_on` | 15 | 20 | Dependency | Prerequisite |
| `throws_error` | 14 | 19 | Error | Debugging, error identification |
| `enables` | 10 | 16 | Dependency (reverse) | Consequence |
| `part_of` | 9 | 13 | Composition | Identification |
| `has_part` | 5 | 13 | Composition | Mechanism |
| `enabled_by` | 7 | 10 | Dependency | Prerequisite |
| `example_of` | 8 | 8 | Example | Identification |
| `has_example` | 2 | 5 | Example | Identification |
| `produces_type` | 6 | 6 | Output | Output prediction |
| `implemented_by` | 3 | 5 | Implementation | Mechanism |
| `is_used_by` | 3 | 4 | Implementation | Mechanism |
| `is_required_by` | 1 | 1 | Dependency | Prerequisite |
| `accepts_type` | 1 | 1 | Input | Input prediction |

An item permits between 2 and 6 relations: median 3, mean 3.35, mode 4. The
distribution is flat rather than peaked — 14 items allow two relations, 14 allow
three, 15 allow four — so no single count is "typical".

## 2. Each relation, and why it is allowed

**`definition` — explanation and identification.** The datatype property carrying
the entity's own text. It supports "explain X" and "which of these describes X",
and it is the only relation that can ground an instance about a single entity
with no neighbour. Allowed for every item.

**`contrasts_with` — comparison, and the one safe distractor source.**
*Instance Attribute (CM_OOP01) contrastsWith Class Attribute (CM_OOP02).* The
ontology asserts that two entities are opposed, which is exactly what a
discrimination question needs. See §4 for why this matters more than its share
of the evidence suggests.

**`depends_on`, `enabled_by`, `is_required_by` — prerequisite questions.**
*Object (COOP002) dependsOn Class (COOP001).* These carry the learning order, so
they support "what must you understand before X". They are the closest thing in
the ontology to a surmise relation, but they are **not** the same thing, and the
item file says so: `lst_requires_policy` forbids converting `depends_on` edges
into LST prerequisites, and every item ships `requires: []` for review.

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

**Inverse pairs.** Where a relation has an `owl:inverseOf`, the ontology asserts
both directions, so about 185 of its 978 triples restate a fact already present.
`contrastsWith` is the exception and is not double-counted here: it is
`owl:SymmetricProperty`, so its two readings are one relation rather than an
inverse pair. Where both directions of a real pair are allowed for an item, the
evidence contains each fact twice, worded differently — a duplicate risk for
§11's near-duplicate metric, not a correctness problem. The same pairing is what
produces the direction mismatch in question 2 of §6.

## 4. Two consequences for generation

**`definition` dominates, and that is a diversity problem.** It supplies 204 of
the 413 collected triples — about half of all evidence, and it is
permitted by all 51 items while no other relation reaches 20. A generator
sampling evidence uniformly will produce mostly explanation instances, and the
required mix of short-answer, true/false and MCQ will come out lopsided. The
mitigation is to weight by relation rather than by triple: choose the relation
role first, then a triple within it.

**Distractors are the hard part, and only 16 items have a safe source.** An MCQ
distractor must be plausible and wrong. The obvious approach — pick another
entity from the item's allowlist — is unsafe, because the allowlist is built from
entities *related* to the anchor, so a distractor drawn from it may well also be
correct. Encapsulation's scope contains both Getter Method and Setter Method, and
both are genuinely its parts, so either is a false distractor for "what is part
of Encapsulation".

`contrasts_with` is the only relation that asserts opposition, which makes its
neighbours plausible and wrong by construction. Only 16 of 51 items permit it.
For the remaining 35, the options are to draw distractors from a different
relation role than the answer (an error type as a distractor for a type question),
or to generate fewer MCQs for those items. This is the substance of review
question 9, and it is unresolved rather than solved.

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

## 6. Open questions for review

1. The item file writes relations in snake_case, the ontology in camelCase, and
   all sixteen differ. `scope_gate.to_owl_property` translates, and a test pins
   the mapping. Should the item file be corrected at source instead?
2. **Five items declare a triple in the direction opposite to their own
   allowlist** — ITEM-024 permits `has_example` and then cites `example_of`;
   ITEM-043 permits `is_used_by` and cites `uses_concept`; ITEM-017 permits
   `is_required_by` and cites `depends_on`. Ten triples in total, across
   ITEM-017, 023, 024, 035 and 043.

   No evidence is lost: the ontology asserts both directions, and the gate holds
   every one of the ten as its inverse. Only the spelling of the direction
   differs. All five items also claim `grounding_status: fully_supported`, which
   is true of the facts and not quite true of the allowlists.

   So: should an allowed relation imply its inverse, given `owl:inverseOf` makes
   them the same edge? Or should the five allowlists be corrected to name the
   direction they cite? The gate currently does neither on its own authority —
   `compare_declared_evidence` reports each mismatch together with the collected
   inverse, and two tests pin the count and the fact that nothing is missing.
3. Should `definition` be weighted down during generation, given it is half the
   evidence and would otherwise dominate the candidate set?
4. For the 35 items without `contrasts_with`, is a cross-role distractor
   acceptable, or should those items generate fewer MCQs?
5. `requires` is empty for all 51 items by policy. When it is filled, should
   `depends_on` inform it, or must it be authored independently?
