import type { components } from "./api.generated";

export type LoanApplication = components["schemas"]["LoanApplication"];
export type ApplicationSummary = components["schemas"]["ApplicationSummary"];
export type ApplicationInput = components["schemas"]["ApplicationInput"];
export type Review = components["schemas"]["ReviewRecord"];
export type Report = components["schemas"]["ReviewReport"];
export type HumanDecision = components["schemas"]["HumanDecision"];
export type RuntimeDetails = components["schemas"]["RuntimeDetails"];
export type Experiment = components["schemas"]["ExperimentRecord"];
export type SampleTemplate = components["schemas"]["SampleTemplate"];
export type ExecutionMode = "offline" | "live";
export type DocumentKind =
  "profit_and_loss" | "bank_transactions" | "business_profile" | "other";
