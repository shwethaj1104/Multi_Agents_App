import type { ReviewMode } from "../types/reviewMode";

/** Read a valid startup preference; the header can change the architecture at runtime. */
export function initialReviewMode(): ReviewMode {
  try {
    const saved = localStorage.getItem("loandesk_review_mode");
    if (saved === "single_agent" || saved === "multi_agent") return saved;
  } catch {
    /* Browser storage can be unavailable; the build preference remains optional. */
  }
  return import.meta.env.VITE_REVIEW_MODE === "multi_agent"
    ? "multi_agent"
    : "single_agent";
}

/** Resolve a public API route per architecture; model/database credentials never enter these URLs. */
export function reviewApiBaseUrl(mode: ReviewMode): string {
  const value =
    mode === "single_agent"
      ? (import.meta.env.VITE_SINGLE_AGENT_API_BASE_URL ??
        "/api/single-agent/v1")
      : (import.meta.env.VITE_MULTI_AGENT_API_BASE_URL ??
        "/api/multi-agent/v1");
  return value.replace(/\/$/, "");
}
