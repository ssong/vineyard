"""Phase output models — typed targets for Pydantic AI agents."""

from typing import Literal

from pydantic import BaseModel, Field


class PhaseOutput(BaseModel):
    """Marker base — every phase output is a Pydantic model."""


class ClarificationQA(BaseModel):
    question: str
    answer: str = "(unanswered)"


class PRDAnalysisOutput(PhaseOutput):
    product_name: str
    product_summary: str = ""
    enriched_prd_markdown: str = ""
    identified_gaps: list[str] = Field(default_factory=list)
    clarification_qa: list[ClarificationQA] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)
    core_problem: str = ""
    mvp_scope_notes: str = ""


class FeatureSpec(BaseModel):
    name: str
    description: str
    priority: Literal["P0", "P1", "P2"]
    user_stories: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    technical_notes: str = ""


class UserFlow(BaseModel):
    name: str
    steps: list[str]


class DesignOutput(PhaseOutput):
    prd_markdown: str = ""
    user_flows: list[UserFlow] = Field(default_factory=list)
    features: list[FeatureSpec] = Field(default_factory=list)
    ui_copy: dict[str, str] = Field(default_factory=dict)
    clarification_qa: list[ClarificationQA] = Field(default_factory=list)


class APIEndpoint(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    description: str
    request_schema: dict = Field(default_factory=dict)
    response_schema: dict = Field(default_factory=dict)
    auth_required: bool = True


class DatabaseColumn(BaseModel):
    name: str
    type: str
    nullable: bool = True


class DatabaseTable(BaseModel):
    name: str
    description: str
    columns: list[DatabaseColumn] = Field(default_factory=list)
    indexes: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)


class EngineeringTask(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    story_points: int = 1
    labels: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class SpecOutput(PhaseOutput):
    technical_spec_markdown: str = ""
    api_endpoints: list[APIEndpoint] = Field(default_factory=list)
    database_schema: list[DatabaseTable] = Field(default_factory=list)
    task_breakdown: list[EngineeringTask] = Field(default_factory=list)
    clarification_qa: list[ClarificationQA] = Field(default_factory=list)


class GeneratedFile(BaseModel):
    path: str
    language: str = "text"


class BuildOutput(PhaseOutput):
    files: list[GeneratedFile] = Field(default_factory=list)
    summary: str = ""
    grader_result: Literal["satisfied", "needs_revision", "max_iterations_reached", "failed", "skipped"] = "skipped"
    grader_explanation: str = ""
    iterations: int = 0
    cost_usd: float = 0.0


class QAOutput(PhaseOutput):
    issues_found: list[str] = Field(default_factory=list)
    issues_fixed: list[str] = Field(default_factory=list)
    issues_unfixable: list[str] = Field(default_factory=list)
    summary: str = ""
