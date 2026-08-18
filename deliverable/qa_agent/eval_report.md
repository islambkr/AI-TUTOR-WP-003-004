# Evaluation report -- COMP101 ontology tutor

Model: `gemma4:e2b-mlx`, temperature 0.  
Cases: 35.  Passed: 30.  Failed: 5.

## By category

| Category | Passed | Total |
| --- | ---: | ---: |
| ambiguity | 2 | 2 |
| definition | 2 | 4 |
| dependency | 5 | 5 |
| dependency-reverse | 2 | 2 |
| empty-result | 3 | 3 |
| listing | 3 | 3 |
| path | 1 | 2 |
| refusal | 3 | 3 |
| relation | 9 | 11 |

## Failures

### 1. What is Encapsulation?

- category: definition
- tools called: ['describe_ontology_entity']
- problems: missing 'COOP_ENC'
- answer: Encapsulation is defined as "Bundling data and behaviour together inside a class, controlling access to enforce invariants." It contrasts with the Global State Problem and depends on Class. It has parts like Getter Method and Setter Method, and it is required by Abstraction and Data Hiding.

### 2. What is Duck Typing?

- category: definition
- tools called: ['describe_ontology_entity']
- problems: missing 'COOP019'
- answer: Duck Typing is Python's implicit form of polymorphism, meaning that if an object has the required method, it can be used regardless of its class, following the principle: "If it walks like a duck and quacks like a duck, it is a duck." It contrasts with Static Typing and depends on concepts like Polymorphism, Interface, `hasattr()`, and `isinstance()`.

### 20. Which error can __eq__ throw?

- category: relation
- tools called: ['find_named_relation']
- problems: missing 'AttributeError'; missing 'E_OOP_ATTR'
- answer: The ontology has no such entity. "__" matches 8 entities. Ask which one is meant. The candidates are: "__dict__ (PI_OOP04)", "__eq__ (MOOP004)", "__init__ (MOOP001)", "__len__ (MOOP005)", "__mro__ (PI_OOP05)", "__repr__ (MOOP003)", "__slots__ (PI_OOP06)", and "__str__ (MOOP002)".

### 21. What are the parts of Encapsulation?

- category: relation
- tools called: ['find_named_relation']
- problems: missing 'Getter Method'; missing 'Setter Method'
- answer: The ontology records none of that relation for it.

### 24. How is Object Identity connected to Class?

- category: path
- tools called: ['find_relation_path']
- problems: missing 'COOP002'
- answer: Object Identity is connected to Class through the following path: Object Identity (COOP_OBJ_ID) dependsOn Object (COOP_OBJ_ID), and Object (COOP_OBJ_ID) dependsOn Class (COOP001).

## All cases

| # | Category | Question | Tools | Result |
| ---: | --- | --- | --- | --- |
| 1 | definition | What is Encapsulation? | describe_ontology_entity | FAIL |
| 2 | definition | What is Duck Typing? | describe_ontology_entity | FAIL |
| 3 | definition | What is a Metaclass? | describe_ontology_entity | pass |
| 4 | definition | What is the Global State Problem? | describe_ontology_entity | pass |
| 5 | dependency | What does Encapsulation depend on? | find_concept_dependencies | pass |
| 6 | dependency | What does Abstraction depend on? | find_concept_dependencies | pass |
| 7 | dependency | What does Duck Typing depend on? | find_concept_dependencies | pass |
| 8 | dependency | What does Abstract Class depend on? | find_concept_dependencies | pass |
| 9 | dependency | What are all the prerequisites of Data Hiding, including indirect ones? | find_concept_dependencies | pass |
| 10 | dependency-reverse | What concepts depend on Class? | find_concept_dependencies | pass |
| 11 | dependency-reverse | What depends on Encapsulation? | find_concept_dependencies | pass |
| 12 | relation | What contrasts with Inheritance? | find_named_relation | pass |
| 13 | relation | What contrasts with Static Typing? | find_named_relation | pass |
| 14 | relation | What enables Instantiation? | find_named_relation | pass |
| 15 | relation | What does Method Overriding enable? | find_named_relation | pass |
| 35 | empty-result | What enables Method Overriding? | find_named_relation | pass |
| 16 | relation | What type does __repr__ produce? | find_named_relation | pass |
| 17 | relation | What type does __eq__ produce? | find_named_relation | pass |
| 18 | relation | What type does __len__ produce? | find_named_relation | pass |
| 19 | relation | Which error can __repr__ throw? | find_named_relation | pass |
| 20 | relation | Which error can __eq__ throw? | find_named_relation | FAIL |
| 21 | relation | What are the parts of Encapsulation? | find_named_relation | FAIL |
| 22 | relation | What is an example of a Dunder Method? | find_named_relation | pass |
| 23 | path | Show a path from Class to Data Hiding. | find_relation_path | pass |
| 24 | path | How is Object Identity connected to Class? | find_relation_path | FAIL |
| 25 | listing | Which errors are covered in this lecture? | list_lecture_entities | pass |
| 33 | listing | List all the skills taught in this lecture. | list_lecture_entities | pass |
| 34 | listing | Which data types are covered? | list_lecture_entities | pass |
| 26 | refusal | What is gradient descent? | describe_ontology_entity | pass |
| 27 | refusal | What is a neural network? | describe_ontology_entity, list_lecture_entities, find_concept_dependencies | pass |
| 28 | refusal | What does gradient descent depend on? | find_concept_dependencies | pass |
| 29 | empty-result | What does __repr__ depend on? | find_concept_dependencies | pass |
| 30 | empty-result | What contrasts with __repr__? | find_named_relation | pass |
| 31 | ambiguity | Tell me about abstract. | describe_ontology_entity | pass |
| 32 | ambiguity | What does abstract depend on? | find_concept_dependencies | pass |
