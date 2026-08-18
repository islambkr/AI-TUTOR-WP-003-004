# Knowledge Graph Reading Notes — AI-TUTOR-WP-003

Sources: W3C RDF 1.1 Concepts and Abstract Syntax (https://www.w3.org/TR/rdf11-concepts/), W3C OWL 2 Web Ontology Language Primer (https://www.w3.org/TR/owl2-primer/), W3C SPARQL 1.1 Query Language (https://www.w3.org/TR/sparql11-query/). Ontology inspected: `comp101_L10.owl`.

## 1. Executive synthesis

An ontology is a formal, explicit specification of a domain's concepts and the relationships between them — a shared, machine-checkable vocabulary, not just documentation. That formality is the reason this project uses one: the AI tutor's agent is a large language model, powerful but probabilistic, with no built-in guarantee that anything it generates is true. The ontology is the opposite — fixed, logical, checkable — and acts as a guardrail on what the agent is allowed to assert as fact. The working rule is that the agent proposes, the ontology permits: the model decides which question to ask and how to phrase the answer, never what the answer is. This combination of a probabilistic neural component and a formal symbolic one is called neurosymbolic AI — the architecture chosen for this Q&A generator project.

That guardrail rests on RDF, RDFS, OWL, and SPARQL, each built directly on the one before it. One thing scopes all four and is worth naming here, even though it is defined with examples in Section 5 below: the open-world assumption, the stance that an absent fact is unknown rather than false. RDF never treats a graph as complete; OWL's reasoning depends on never treating silence as "no."

RDF is the foundation: a data model, not a file format. It reduces information to triples — subject, predicate, object — forming a graph. Subjects and predicates are IRIs (globally unique names, similar to URLs but not required to resolve); objects can also be literals (self-contained values) or blank nodes (anonymous, structure without identity). Namespaces/prefixes shorten IRIs — `oop:courseId` isn't itself valid, it expands to the namespace IRI plus a local name. `comp101_L10.owl` uses RDF/XML — the one syntax OWL 2 requires every conformant tool to support; the same ontology in Turtle would produce an identical graph — syntax is packaging, the triples are the meaning.

RDFS is a small vocabulary written using RDF's own triple model to add the minimum structure needed for a schema: classes, a subclass hierarchy, property domain/range, and human-readable labels and comments. RDFS is not something OWL replaces — OWL directly reuses RDFS's own terms (`rdfs:label`, `rdfs:domain`, `rdfs:range`,  `rdfs:comment`) rather than redefining equivalents, because RDFS already solved basic hierarchy modeling adequately.

OWL extends RDFS with the logical machinery that makes the ontology a guardrail, not just documentation. An ontology is built from axioms (asserted statements), entities (individuals, classes, and object/datatype/annotation properties), and expressions (combinations of entities into complex class descriptions). Declaring a property transitive or symmetric — as `dependsOn` and `contrastsWith` are here — lets a reasoner (HermiT) derive new facts automatically, much like a Prolog program deriving `ancestor(X,Y)` from a rule over `parent/2` facts. The comparison is useful exactly where it breaks: Prolog by default resolves an unprovable goal as false (closed-world, negation-as-failure), while OWL treats it as merely unknown (open-world, as above) — silence is never evidence of absence. This is also why negative facts (`DisjointClasses`, `DifferentIndividuals`, `NegativeObjectPropertyAssertion`) must be asserted directly, never inferred from an absence a Prolog rule would treat as failure.

SPARQL is the query layer on top: it matches graph patterns — triple templates with variables — against the graph's triples, rather than joining tables like SQL, needing no fixed schema. Its standout feature is property paths: querying connectivity across an arbitrary number of hops (`dependsOn+`) instead of a fixed join depth, turning multi-hop traversal into one expression instead of a chain of joins.

This is the mechanism behind "the agent proposes, the ontology permits": SPARQL is how the agent's tool calls reach the graph, so every answer is traceable to an asserted or reasoner-derived fact, never the model's own training.

## 2. RDF vs. RDFS vs. OWL vs. SPARQL

| | RDF | RDFS | OWL | SPARQL |
|---|---|---|---|---|
| **What it is** | Core data model: triples, IRIs, literals, blank nodes | A vocabulary (written in RDF) for basic schema structure | A much richer vocabulary (written in RDF) for formal logic | The query language for RDF graphs |
| **Role in the stack** | Foundation — how any statement is represented | Adds minimal structure on top of RDF | Adds real logical semantics on top of RDFS | Sits on top, retrieves from whatever RDF/RDFS/OWL data exists |
| **Key constructs** | Triple, IRI, literal, blank node, namespace | `rdfs:Class`, `rdfs:subClassOf`, `rdfs:domain`, `rdfs:range`, `rdfs:label`, `rdfs:comment` | Axioms, individuals, classes, object/datatype/annotation properties, disjointness, property characteristics (symmetric, transitive, inverse...) | Basic graph patterns, `FILTER`, property paths, `SELECT`/`ASK`/`CONSTRUCT`/`DESCRIBE` |
| **Can it reason/infer?** | No — just states facts | Very limited (subclass/subproperty transitivity) | Yes — full entailment and consistency checking via a reasoner (e.g. HermiT) | No — retrieves what's already asserted (or already inferred, if queried through a reasoner-backed store) |
| **Example from `comp101_L10.owl`** | `oop:MOOP003 rdfs:label "__repr__"` | `oop:courseId rdfs:domain owl:Thing` | `oop:contrastsWith` declared `owl:SymmetricProperty`; `owl:AllDisjointClasses` over the 14 top-level classes | `oop:COOP009 oop:dependsOn+ ?dep` — transitive dependency traversal from "Data Hiding" |

## 3. Five examples of asserted facts

1. `oop:MOOP003 rdf:type oop:Method` — `__repr__` is a Method.
2. `oop:COOP009 oop:dependsOn oop:COOP_ENC` — "Data Hiding" depends on "Encapsulation".
3. `oop:MR_OOP01 oop:contrastsWith oop:MR_OOP02` — "Getter Method" contrasts with "Setter Method".
4. `oop:MOOP002 oop:producesType oop:DT_OOP_STR` — `__str__` produces `str`.
5. `oop:contrastsWith rdf:type owl:SymmetricProperty` — `contrastsWith` is declared symmetric. This is itself an asserted fact, at the schema level rather than about a specific individual — it's what makes example 2 in Section 4 possible.

## 4. Five examples of inferred facts

1. `oop:COOP009 oop:dependsOn oop:COOP001` — "Data Hiding" depends on "Class". Not written anywhere in the file; derived because `dependsOn` is `owl:TransitiveProperty` and the two-hop chain Data Hiding → Encapsulation → Class is asserted.
2. `oop:Method rdfs:subClassOf oop:TypeProducer` — nowhere in the file is `Method` declared a subclass of anything. It follows from `TypeProducer` being declared `owl:equivalentClass` to the union of `Method`, `BuiltInFunction` and `Algorithm`: if the union *is* `TypeProducer`, then each member class must sit underneath it. The same reasoning gives `Method`, `LanguageConstruct`, `OOPMechanism` and `PythonInternals` as subclasses of `ImplementorType`.
3. `oop:FOOP001 rdf:type oop:TypeProducer` — `super()` is asserted only as a `BuiltInFunction`. Its membership of `TypeProducer` is derived from the same union axiom, one level down: class membership flows to the individuals. 27 individuals gain a type this way, and none of those types is written in the file.
4. Any individual with an asserted `oop:cognitiveType` value is entailed `rdf:type oop:Concept`, because `cognitiveType`'s declared domain is `oop:Concept`. Worth stating carefully: this is a valid entailment, but in *this* file it adds nothing new — all 11 individuals carrying a `cognitiveType` are already explicitly typed `Concept`. Domain and range are only useful as inference rules when the data leaves the type unstated, which is a modelling choice this ontology did not make.
5. Because the 14 top-level classes are declared `owl:AllDisjointClasses`, a reasoner can also infer *negative* facts: `oop:MOOP003` (asserted a `Method`) is inferred to **not** be a `Concept`, a `DataType`, an `ErrorType`, or any of the other 13 classes — an exclusion, not just a new positive statement.

## 5. The open-world assumption, with two examples

The open-world assumption is the stance that an absent fact is unknown, not false — the opposite of a database's closed-world default, where a missing row means "no." An ontology never claims to be complete, so silence by itself carries no information about truth.

**Example 1 — a missing relation between two entities the ontology does know about.** `oop:MOOP001` (`__init__`) has no `oop:producesType` triple anywhere in this file, while its neighbours do — `__str__` produces `str`, `__eq__` produces `bool`, `__len__` produces `int`. Under open-world semantics that absence does not mean "the ontology asserts `__init__` produces nothing"; it means the fact was simply never recorded. A query for `__init__`'s produced type correctly returns no result, but that result has to be read as "not stated," never as "false." The contrast with its siblings is what makes the point sharp: a closed-world database would let you conclude "`__init__` returns nothing" from the same silence.

**Example 2 — an entity the ontology has no record of at all.** There is no entity for "gradient descent" anywhere in this ontology. Its absence does not mean the ontology asserts gradient descent doesn't exist or isn't relevant to OOP — it means the ontology simply has no information about it. This is exactly why the agent (per the work package's required test questions) must answer "not found in the ontology" rather than inventing a plausible-sounding answer or claiming the concept is false: an open-world system is never entitled to conclude non-existence from silence.

## 6. Five questions the ontology can answer

Each of these maps onto triples that are actually present, which is why the graph service can answer them without a language model inventing anything.

1. **"What is Encapsulation?"** — `oop:COOP_ENC oop:definition "Bundling data and behaviour together inside a class, controlling access to enforce invariants."` A single datatype-property lookup.
2. **"What does Data Hiding need me to understand first?"** — `oop:dependsOn` gives Encapsulation and Name Mangling directly; because `dependsOn` is `owl:TransitiveProperty`, the chain also reaches Class. Answerable at one hop or all hops depending on which the student wants.
3. **"Which errors can `__eq__` raise?"** — `oop:MOOP004 oop:throwsError oop:E_OOP_ATTR` (AttributeError). The same shape answers the produced-type question via `oop:producesType`.
4. **"What is commonly confused with Inheritance?"** — `oop:contrastsWith` links it to Composition and Interface. This is the pedagogically interesting one: it encodes *misconception risk*, not just structure.
5. **"How is Class connected to Data Hiding?"** — a two-step chain, Encapsulation depends on Class and Data Hiding depends on Encapsulation. The connection exists in the graph even though no single triple states it.

The common thread: each is a question about *what relates to what*, which is precisely what a graph stores.

## 7. Five questions the ontology cannot answer

These are the more useful list, because they mark the boundary the agent must refuse to cross.

1. **"Why does Data Hiding depend on Encapsulation?"** The graph records *that* the dependency holds and never *why*. `oop:dependsOn` is a link with no explanation attached, and there is no property in the file that could carry one. The agent can report the dependency and must not manufacture a justification.
2. **"Which entities are TypeProducers?"** Asked against the asserted triples alone, the answer is none — every `TypeProducer` membership is inferred through the `owl:unionOf` axiom. The ontology *contains* the answer, but only a reasoner can extract it; a plain SPARQL query over the file returns nothing. This is the sharpest illustration of asserted versus inferred in the whole project.
3. **"In what order should I study these concepts, and which is hardest?"** There is no ordering, difficulty, or duration property anywhere in the file — I checked the full predicate list. `oop:cognitiveType` looks like it might help but is a *kind* label, not a scale: it takes only the values "conceptual" (10 individuals) and "procedural" (1), so it cannot rank anything.
4. **"Show me code that implements a getter."** The ontology holds definitions and relations, never source code. `oop:bestPractice` exists but is asserted exactly once in the entire file, so even prose guidance is almost absent.
5. **"Does this appear on the exam, and how many marks is it worth?"** Nothing about assessment, scheduling, or the students themselves is modelled. The ontology describes lecture content, not the course as an institution.

Categories 1 and 5 are absent by design; 2 is present but needs reasoning; 3 and 4 are gaps that could be filled by adding properties, if the tutor ever needs them.

## 8. Open questions for the review meeting

1. **Should the graph service run a reasoner?** It currently answers only from facts written in the file. Some facts are not written but follow logically — every Method is also a TypeProducer, because TypeProducer is defined as the union of Method, BuiltInFunction and Algorithm. Since I do not reason, asking "which entities are TypeProducers?" returns nothing. Should the tutor teach what is stated, or also what follows?

2. **How should the agent's accuracy be reported, when it is not repeatable?** The graph service returns the same answer every time. The agent does not: identical code scored between 14 and 32 out of 34 on different runs, at temperature 0. I report a range rather than one figure.

3. **Was it right to ignore `oop:teaches` when searching for paths?** The lecture is connected to all 66 entities, so without excluding it every pair of concepts is two steps apart through the lecture — true, but it tells a student nothing. I excluded it so paths show concept-to-concept routes. That was my judgement about usefulness, not something the ontology states.

4. **Should the ontology keep asserting both directions of every relation?** The file writes both "A teaches B" and "B taughtIn A", and does the same for all ten inverse pairs. A reasoner would derive the second from the first. Keeping both makes the file usable without a reasoner, but every hand edit has to be made twice or the graph contradicts itself.
