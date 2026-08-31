"""schemas.py -- the typed contracts of the WP-004 pipeline.

Every value that crosses a stage boundary is a Pydantic model, so a malformed
record fails where it is produced rather than somewhere downstream. The
generator's output in particular is never accepted as free text: it must parse
into CandidateInstance or it is rejected.

The models here cover the four stages named in the work package: the input item,
the scope computed for it, the evidence that scope permits, and the candidate
instance a model proposes from it.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InstanceType = Literal["short_answer", "true_false", "mcq"]


class EvidenceTriple(BaseModel):
    """One ontology fact, written subject-predicate-object.

    Subject and predicate are always entity/property identifiers. The object is
    an identifier for an object property and a literal for a datatype property
    such as `definition`, which is why it is typed as a plain string.
    """

    model_config = ConfigDict(frozen=True)

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
    """

    anchor_ids: list[str]
    allowed_entity_ids: list[str]
    allowed_relation_ids: list[str]
    max_depth: int = 1


class Item(BaseModel):
    """One Learning Space Theory item: a problem *type*, not a problem.

    "Explain what a class represents" is an item. "Explain what the Car class in
    this snippet represents" would be one of its instances. One item admits many
    instances, which is the whole reason this pipeline generates rather than
    stores them.
    """

    id: str
    title: str
    description: str
    requires: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    ontology_gate: OntologyGate


class OntologyScope(BaseModel):
    """What one item is allowed to draw on, resolved against the ontology.

    Built by scope_gate.build_scope. `allowed_relations` holds OWL property
    names, already normalised from the snake_case used in the item file; the
    evidence is every permitted fact actually asserted in the graph.
    """

    item_id: str
    anchors: list[str]
    max_depth: int
    allowed_entities: set[str]
    allowed_relations: set[str]
    evidence: list[EvidenceTriple]


class CandidateInstance(BaseModel):
    """One generated instance, before any validation has been applied.

    Field names are fixed by the work package. `extra="forbid"` matters: a model
    that invents a field is producing output the pipeline does not understand,
    and that is a malformed-output rejection rather than something to paper over.
    """

    model_config = ConfigDict(extra="forbid")

    item_id: str
    instance_type: InstanceType
    prompt: str
    answer_key: str
    choices: list[str] | None = None
    ontology_entities_used: list[str] = Field(default_factory=list)
    ontology_evidence: list[EvidenceTriple] = Field(default_factory=list)
    generation_notes: str | None = None

    @model_validator(mode="after")
    def _choices_belong_to_mcq_only(self) -> "CandidateInstance":
        """Choices are required for an MCQ and forbidden everywhere else.

        A short-answer instance carrying choices is not a harmless extra: it
        means the model produced a different question type from the one asked
        for, which the caller needs to see as an error.
        """
        if self.instance_type == "mcq":
            if not self.choices or len(self.choices) < 2:
                raise ValueError("an mcq needs at least two choices")
            if self.answer_key not in self.choices:
                raise ValueError("the answer key of an mcq must be one of its choices")
        elif self.choices is not None:
            raise ValueError(f"{self.instance_type} must not carry choices")
        return self


class ValidationResult(BaseModel):
    """The outcome of one validation pass over one candidate.

    `kind` records whether this verdict is deterministic or a model judgement.
    The work package requires the two to be reported separately, and keeping the
    distinction on the record itself is what makes that possible later.
    """

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
