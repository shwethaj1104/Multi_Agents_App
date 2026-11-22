from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

ReviewMode = Literal["single_agent", "multi_agent"]
ExecutionMode = Literal["offline", "live"]
DocumentKind = Literal["profit_and_loss", "bank_transactions", "business_profile", "other"]


# Generate a timezone-aware timestamp shared by persisted records and audit entries.
def utc_now() -> str:
    return datetime.now(UTC).isoformat()


# Generate opaque server IDs; callers cannot select database keys or checkpoint thread IDs.
def new_id() -> str:
    return str(uuid4())


class ApplicationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_name: str = Field(min_length=2, max_length=120)
    industry: str = Field(min_length=2, max_length=80)
    amount: Decimal = Field(gt=0, le=Decimal("10000000"), max_digits=12, decimal_places=2)
    purpose: str = Field(min_length=5, max_length=1500)
    operating_months: int = Field(ge=0, le=1200)
    term_months: int = Field(default=36, ge=6, le=120)
    annual_interest_rate: Decimal = Field(default=Decimal("8"), ge=0, le=50)
    currency: Literal["AED"] = "AED"


class EvidenceDocument(BaseModel):
    id: str = Field(default_factory=new_id)
    filename: str
    kind: DocumentKind
    text: str
    sha256: str
    storage_name: str
    pages: int = 1
    created_at: str = Field(default_factory=utc_now)


class LoanApplication(ApplicationInput):
    workspace_mode: ReviewMode | None = None
    id: str = Field(default_factory=new_id)
    version: int = 1
    is_sample: bool = False
    documents: list[EvidenceDocument] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class Finding(BaseModel):
    code: str
    category: Literal["documents", "financial", "policy"]
    severity: Literal["info", "warning", "blocking"]
    message: str
    evidence_ids: list[str] = Field(default_factory=list)
    policy_clause: str | None = None


class AgentAssessment(BaseModel):
    finding_codes: list[str] = Field(default_factory=list)
    follow_up_agents: list[Literal["document_reviewer", "financial_analyst", "policy_reviewer"]] = (
        Field(default_factory=list)
    )
    summary: str = Field(max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class ReviewReport(BaseModel):
    agent_finding_codes: list[str] = Field(default_factory=list)
    agent_evidence_ids: list[str] = Field(default_factory=list)
    revision: int
    title: str
    summary: str
    recommendation: Literal["ready_for_officer", "needs_information", "policy_exception"]
    findings: list[Finding]
    financials: dict[str, str | None]
    sources: list[dict[str, str]]
    policy_version: str
    limitations: list[str]
    human_note: str = ""


class ReviewRequest(BaseModel):
    execution_mode: ExecutionMode = "live"


class HumanDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["approve", "reject", "request_changes", "provide_information"]
    revision: int = Field(ge=1)
    reviewer: str = Field(min_length=2, max_length=100)
    note: str = Field(default="", max_length=3000)
    idempotency_key: str = Field(default_factory=new_id, max_length=100)


class ReviewRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    case_id: str
    case_version: int
    review_mode: ReviewMode
    execution_mode: ExecutionMode
    status: str = "queued"
    report: ReviewReport | None = None
    events: list["TraceEvent"] = Field(default_factory=list)
    decisions: list[dict] = Field(default_factory=list)
    usage: "UsageSummary" = Field(default_factory=lambda: UsageSummary())
    processing_seconds: float = 0
    human_wait_seconds: float = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    waiting_since: str | None = None
    trace_id: str | None = None
    trace_url: str | None = None
    error: str | None = None
    pending_resume: dict | None = None
    version: int = 1


class DomainError(Exception):
    # Carry a safe public error message without leaking provider/connection exception details.
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class ApplicationSummary(ApplicationInput):
    review_status: str = "not_reviewed"
    workspace_mode: ReviewMode | None = None
    id: str
    version: int
    is_sample: bool
    created_at: str
    updated_at: str
    document_count: int


class RuntimeDetails(BaseModel):
    review_mode: ReviewMode
    implementation_stage: str
    storage: str
    model: str
    live_calls_enabled: bool
    tracing_configured: bool
    authentication: str
    policy_version: str


class TraceEvent(BaseModel):
    id: str
    name: str
    role: str
    at: str
    duration_seconds: float | None = None
    attempt_id: str | None = None
    model: str | None = None
    estimated_cost_usd: float | None = None
    error_code: str | None = None
    usage: dict | None = None


class UsageSummary(BaseModel):
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    unknown_usage_calls: int = 0
    estimated_cost_usd: float | None = None
    cost_kind: str = "not_started"


class SampleTemplate(BaseModel):
    key: str
    business_name: str
    description: str


class ExperimentRow(BaseModel):
    sample_key: str
    case_id: str
    review_id: str
    review_mode: ReviewMode
    status: str
    processing_seconds: float
    usage: UsageSummary
    scores: dict[str, float]
    trace_url: str | None = None


class ExperimentRecord(BaseModel):
    id: str
    version: int
    status: str
    created_at: str
    execution_mode: ExecutionMode
    dataset_version: str
    dataset_split: str
    case_limit: int
    rows: list[ExperimentRow]
    summary: dict[str, dict[str, float | None]]
    interpretation: str
    langsmith_published: bool = False
    langsmith_dataset_url: str | None = None
    langsmith_projects: dict[str, str | None] = Field(default_factory=dict)
    finished_at: str | None = None
    error: str | None = None


ReviewRecord.model_rebuild()
