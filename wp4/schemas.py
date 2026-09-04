"""schemas.py -- the typed contracts of the WP-004 pipeline.

Every value that crosses a stage boundary is a Pydantic model, so a malformed
record fails where it is produced rather than somewhere downstream. The
generator's output in particular is never accepted as free text: it must parse
into one of the CandidateInstance variants or it is rejected.

Every model here forbids unknown fields. An unexpected key means the producer
and this contract disagree, and that is worth an error whether the producer is a
language model inventing a field or an item file carrying one nobody modelled.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

#: The type of instance to generate. Not a field on any model here -- each
#: variant pins its own `instance_type` -- but the generator takes it as the
#: "requested instance type" input the work package names in section 10.4.
InstanceType = Literal["short_answer", "true_false", "mcq"]

#: Shared by every model below. Kept in one place so the rule cannot drift.
STRICT = ConfigDict(extra="forbid")


class EvidenceTriple(BaseModel):
    """One ontology fact, written subject-predicate-object.

    Subject and predicate are always entity/property identifiers. The object is
    an identifier for an object property and a literal for a datatype property
    such as `definition`, which is why it is typed as a plain string.
    """

    model_config = ConfigDict(**STRICT, frozen=True)

    subject: str
    predicate: str
    object: str

    def __str__(self) -> str:
        return f"{self.subject} {self.predicate} {self.object}"


class OntologyGate(BaseModel):
    """The allowlist an item carries in the item file.

    This is mentor-approved input, not something the pipeline derives. The gate
    is deliberately an explicit allowlist rather than a traversal result: the
    work package requires that scope never depends on a model's judgement, and
    an allowlist cannot drift.

    `evidence_triples` and `grounding_status` are the item file's own record of
    what supports the item. The gate resolves its evidence from the ontology
    rather than trusting this field, and scope_gate.compare_declared_evidence
    reports where the two disagree.
    """

    model_config = STRICT

    anchor_ids: list[str] = Field(min_length=1)
    allowed_entity_ids: list[str]
    allowed_relation_ids: list[str]
    # Every item ships depth 1. The bound is a guard against a hand-edited file
    # asking for a traversal nobody intended, not a description of the data.
    max_depth: int = Field(default=1, ge=0, le=5)
    evidence_triples: list[tuple[str, str, str]] = Field(default_factory=list)
    # Every one of the 51 items claims fully_supported -- including the five
    # that declare a triple their own allowlist does not permit. A Literal keeps
    # a new value from passing unnoticed if the file gains one.
    grounding_status: Literal["fully_supported"] | None = None


class Item(BaseModel):
    """One Learning Space Theory item: a problem *type*, not a problem.

    "Explain what a class represents" is an item. "Explain what the Car class in
    this snippet represents" would be one of its instances. One item admits many
    instances, which is the whole reason this pipeline generates rather than
    stores them.
    """

    model_config = STRICT

    id: str
    title: str
    description: str
    requires: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    ontology_gate: OntologyGate

    def __str__(self) -> str:
        return f"{self.id} -- {self.title}"


class OntologyScope(BaseModel):
    """What one item is allowed to draw on, resolved against the ontology.

    Built by scope_gate.build_scope. `allowed_relations` holds OWL property
    names, already normalised from the snake_case used in the item file; the
    evidence is every permitted fact actually asserted in the graph.
    """

    model_config = STRICT

    item_id: str
    anchors: list[str]
    max_depth: int
    allowed_entities: set[str]
    allowed_relations: set[str]
    evidence: list[EvidenceTriple]

    def __str__(self) -> str:
        return (
            f"{self.item_id}  anchors={','.join(self.anchors)}  "
            f"entities={len(self.allowed_entities)}  "
            f"relations={','.join(sorted(self.allowed_relations))}  "
            f"evidence={len(self.evidence)}"
        )


class _InstanceBase(BaseModel):
    """Fields every generated instance carries, whatever its type."""

    model_config = STRICT

    item_id: str
    prompt: str
    answer_key: str
    ontology_entities_used: list[str] = Field(default_factory=list)
    ontology_evidence: list[EvidenceTriple] = Field(default_factory=list)
    generation_notes: str | None = None


class ShortAnswerInstance(_InstanceBase):
    # Defaulted rather than required: there is exactly one valid value, and a
    # small model asked to fill it simply omitted the field. The Literal still
    # pins it, so the discriminated union is unaffected.
    instance_type: Literal["short_answer"] = "short_answer"


class TrueFalseInstance(_InstanceBase):
    """A true/false instance, whose answer is one of exactly two words.

    Narrowing `answer_key` here is the point of having a separate variant: a
    model that replies "maybe, it depends" has not answered a true/false
    question, and the schema says so rather than a grader discovering it later.
    """

    instance_type: Literal["true_false"] = "true_false"
    answer_key: Literal["true", "false"]


class MCQInstance(_InstanceBase):
    """A multiple-choice instance, the only variant that carries choices.

    Modelling the three types separately rather than as one class with an
    optional field means a short answer cannot hold choices at all: the field
    does not exist on it, so the error comes from the schema instead of from a
    validator that has to remember the rule.
    """

    instance_type: Literal["mcq"] = "mcq"
    choices: list[str] = Field(min_length=2)

    @model_validator(mode="after")
    def _answer_is_one_of_the_choices(self) -> "MCQInstance":
        if self.answer_key not in self.choices:
            raise ValueError("the answer key of an mcq must be one of its choices")
        return self

    @model_validator(mode="after")
    def _choices_are_distinct(self) -> "MCQInstance":
        """Two identical choices are one choice, and a duplicate answer is two
        correct answers. Section 11 measures near-duplicates in the candidate
        set; a duplicate inside a single question is the same defect, smaller."""
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("the choices of an mcq must be distinct")
        return self


#: A stored candidate of any type. The discriminator lets Pydantic pick the
#: variant from `instance_type` alone, so a malformed record is rejected against
#: the right schema rather than against all three in turn.
#:
#: This is the type for *reading* records. Do not hand it to the model as a
#: structured-output schema: it compiles to `oneOf` plus a discriminator, and
#: small local models fill branching schemas unreliably. The generator knows
#: which type it asked for, so it should pass the concrete variant
#: (MCQInstance, and so on) and keep this union for parsing what comes back.
CandidateInstance = Annotated[
    ShortAnswerInstance | TrueFalseInstance | MCQInstance,
    Field(discriminator="instance_type"),
]

#: Use to parse untrusted input: `CANDIDATE_INSTANCE.validate_python(payload)`.
CANDIDATE_INSTANCE = TypeAdapter(CandidateInstance)

#: The variant to request from the model for a given instance type.
INSTANCE_MODELS: dict[str, type[_InstanceBase]] = {
    "short_answer": ShortAnswerInstance,
    "true_false": TrueFalseInstance,
    "mcq": MCQInstance,
}


class GenerationInput(BaseModel):
    """Exactly what the model was shown, kept so a candidate can be re-made.

    The work package is strict that the model sees only this -- never the full
    ontology -- so recording it is what makes that claim checkable after the
    fact rather than a description of intent.
    """

    model_config = STRICT

    item_id: str
    item_title: str
    item_description: str
    instance_type: InstanceType
    allowed_entities: list[str]
    allowed_relations: list[str]
    evidence: list[EvidenceTriple]
    model_name: str


class CandidateRecord(BaseModel):
    """One candidate and everything that happened to it -- the section 10.7 row.

    Rejected candidates stay in the dataset with their reason attached, so the
    six fields below are all optional-on-failure rather than absent: a record
    whose generation failed still carries its input and its reason.

    `ungrounded_distractors` is a signal, not a verdict. Distractors may be
    invented, and counting how often that happens is what allows the comparison
    between the items that carry a `contrastsWith` edge and those that do not.
    """

    model_config = STRICT

    generation_input: GenerationInput
    raw_output: str | None = None
    instance: ShortAnswerInstance | TrueFalseInstance | MCQInstance | None = None
    ontology_validation: "ValidationResult | None" = None
    pedagogical_validation: "ValidationResult | None" = None
    ungrounded_distractors: list[str] = Field(default_factory=list)
    # True when the model returned no citations and the generator attached the
    # evidence it had supplied. Recorded rather than hidden: it means the
    # fabricated-citation check had nothing of the model's own to judge.
    evidence_attached: bool = False
    human_decision: Literal["accepted", "rejected", "unreviewed"] = "unreviewed"
    rejection_reason: str | None = None

    @property
    def item_id(self) -> str:
        return self.generation_input.item_id

    @property
    def passed_ontology(self) -> bool:
        return bool(self.ontology_validation and self.ontology_validation.passed)


class ValidationResult(BaseModel):
    """The outcome of one validation pass over one candidate.

    `kind` records whether this verdict is deterministic or a model judgement.
    The work package requires the two to be reported separately, and keeping the
    distinction on the record itself is what makes that possible later.

    Section 10.7 also requires a final human-review field. It is deliberately
    not here: a human decision is made once per candidate, not once per
    validation pass, so it belongs on the stored candidate record that step 10.8
    builds -- alongside the generation input, both verdicts, and the rejection
    reason. Recorded here so it is not lost between the two steps.
    """

    model_config = STRICT

    item_id: str
    kind: Literal["ontology", "pedagogical"]
    passed: bool
    failures: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _failures_match_the_verdict(self) -> "ValidationResult":
        if self.passed and self.failures:
            raise ValueError("a passing result cannot list failures")
        if not self.passed and not self.failures:
            raise ValueError("a failing result must say why")
        return self


CandidateRecord.model_rebuild()
