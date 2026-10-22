from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictModel):
    page: int = Field(ge=1)
    quote: str = Field(max_length=600)


class MethodStep(StrictModel):
    title: str
    instruction: str
    citations: list[Citation] = Field(default_factory=list)


class Extraction(StrictModel):
    title: str
    summary: str
    assay: str
    materials: list[str]
    steps: list[MethodStep]
    unknowns: list[str]
    readout: str


class Operation(StrictModel):
    action: Literal["transfer", "mix"]
    source: str = ""
    destinations: list[str] = Field(min_length=1, max_length=96)
    volume_ul: float = Field(gt=0, le=10000, allow_inf_nan=False)
    cycles: int = Field(default=3, ge=1, le=30, description="Only used for action=mix. It does not repeat a transfer.")
    mix_after_ul: float = Field(default=0, ge=0, le=120, allow_inf_nan=False, description="For transfer: mix immediately after dispensing using the same attached tip. Prefer this to a separate mix operation when the method uses the same tip.")
    mix_after_cycles: int = Field(default=3, ge=1, le=30)
    source_height: float = Field(default=0, allow_inf_nan=False, description="Relative offset in mm from the supplied source anchor; zero uses the configured anchor, not an unspecified coordinate.")
    destination_height: float = Field(default=0, allow_inf_nan=False, description="Relative offset in mm from the supplied destination anchor; zero uses the configured anchor.")
    purpose: str
    citations: list[Citation] = Field(default_factory=list)


class ManualStep(StrictModel):
    when: Literal["before", "after", "between"]
    instruction: str
    reason: str


class StockPreparation(StrictModel):
    position: str = Field(min_length=1, max_length=200)
    material: str = Field(min_length=1, max_length=200)
    concentration: str = Field(default="", max_length=300, description="Concentration of the liquid the HUMAN loads, with units; not the final assay concentration. Unknown samples may explicitly have unknown concentration.")
    preparation: str = Field(default="", max_length=2500, description="Human recipe or ready-to-use instruction. Preserve unknowns; do not assume an unavailable parent-stock concentration.")
    load_volume_ul: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False, description="Optional proposed initial load. Omit to calculate demand plus a preparation reserve. Must fit actual configured capacity.")
    citations: list[Citation] = Field(default_factory=list)


class Plan(StrictModel):
    title: str
    summary: str
    operations: list[Operation] = Field(max_length=100, description="Return an empty list when the source or setup cannot support a defensible liquid-handling plan; explain the blockers in unresolved rather than inventing actions.")
    manual_steps: list[ManualStep] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    stock_preparations: list[StockPreparation] = Field(default_factory=list, max_length=100)


class Finding(StrictModel):
    severity: Literal["critical", "warning", "info"]
    title: str
    detail: str
    operation_index: int | None = None
    citations: list[Citation] = Field(default_factory=list)


class Review(StrictModel):
    summary: str
    verdict: Literal["changes_required", "needs_operator_review", "no_issues_found"]
    findings: list[Finding] = Field(max_length=12)
    questions: list[str] = Field(max_length=12)


class SetupInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    gantry_yaml: str = Field(max_length=300000)
    deck_yaml: str = Field(max_length=300000)
    fluids_yaml: str = Field(default="", max_length=300000)
    materials: str = Field(default="", max_length=10000)
    first_tip: str = Field(default="A1", pattern=r"^[A-H](?:[1-9]|1[0-2])$")
    nominal_vial_capacity_ul: float = Field(default=5000, gt=0, le=100000, allow_inf_nan=False)


class RunInput(StrictModel):
    paper_id: str
    setup_id: str = "picus120"
    objective: str = Field(min_length=5, max_length=6000)
    review_enabled: bool = True


class ProtocolEdit(StrictModel):
    protocol_yaml: str = Field(min_length=1, max_length=500000)


class EvidenceInput(StrictModel):
    video_id: str | None = None
    offset_seconds: float = Field(default=0, allow_inf_nan=False)
    markers: list[dict] = Field(default_factory=list, max_length=1000)
    notes: str = Field(default="", max_length=10000)


class HandoffInput(StrictModel):
    mock_mode: bool = True
    expected_hash: str
    operator_confirmed: bool = False
    manual_steps_confirmed: bool = False
    setup_confirmed: bool = False
    preparation_hash: str | None = None


class PreparationEdit(StrictModel):
    expected_hash: str
    stocks: list[StockPreparation] = Field(max_length=100)


class LoadingConfirmation(StrictModel):
    expected_preparation_hash: str
    loaded_positions: list[str] = Field(max_length=100)
    human_steps_confirmed: bool = False


class RubricInput(StrictModel):
    reviewer: str = ""
    approved: bool = False
    criteria: list[dict] = Field(default_factory=list, max_length=100)


class AdjudicationInput(StrictModel):
    expected_hash: str
    reviewer: str = Field(min_length=1, max_length=100)
    notes: str = Field(min_length=20, max_length=10000)
    finding_responses: dict[str, str] = Field(default_factory=dict)
    question_responses: dict[str, str] = Field(default_factory=dict)
    approved: bool = False
