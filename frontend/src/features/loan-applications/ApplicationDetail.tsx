import { useState } from "react";
import { useAppDispatch, useAppSelector } from "../../app/hooks";
import { caseSelected } from "../../app/workspaceSlice";
import { Button } from "../../components/ui/Button";
import {
  ErrorState,
  LoadingState,
  errorMessage,
  formatMoney,
  statusLabel,
} from "../../components/ui/Feedback";
import {
  useGetApplicationQuery,
  useGetReviewsQuery,
  useGetRuntimeQuery,
  useRecoverReviewMutation,
  useStartReviewMutation,
} from "../../services/api/loanDeskApi";
import { HumanDecisionPanel } from "../human-approvals/HumanDecisionPanel";
import { ReviewReportView } from "../loan-reviews/ReviewReportView";
import { ReviewTimeline } from "../loan-reviews/ReviewTimeline";
import { EvidencePanel } from "./EvidencePanel";

/** Connect a saved application, source evidence, review progress and revision-bound human actions. */
export function ApplicationDetail({ caseId }: { caseId: string }) {
  const dispatch = useAppDispatch();
  const preferredReview = useAppSelector(
    (state) => state.workspace.activeReviewId,
  );
  const {
    data: application,
    error,
    isLoading,
    refetch,
  } = useGetApplicationQuery(caseId);
  const { data: reviews = [] } = useGetReviewsQuery(caseId, {
    pollingInterval: 1500,
  });
  const { data: runtime } = useGetRuntimeQuery();
  const [startReview, { isLoading: starting }] = useStartReviewMutation();
  const [recoverReview, { isLoading: recovering }] = useRecoverReviewMutation();
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null);
  const [chosenReview, setChosenReview] = useState<string | null>(
    preferredReview,
  );
  const [failure, setFailure] = useState("");
  const review = reviews.find((item) => item.id === chosenReview) ?? reviews[0];
  const busy =
    starting ||
    !!reviews.find((item) =>
      ["queued", "running", "resuming"].includes(item.status ?? ""),
    );
  /** Start a live review on explicit click; the backend still enforces enablement and spending limits. */
  async function beginReview() {
    setFailure("");
    try {
      const result = await startReview({
        caseId,
        executionMode: "live",
      }).unwrap();
      setChosenReview(result.id!);
    } catch (issue) {
      setFailure(errorMessage(issue));
    }
  }
  /** Resume persisted interrupted work only after an explicit operator request. */
  async function recover() {
    setFailure("");
    try {
      await recoverReview(review.id!).unwrap();
    } catch (issue) {
      setFailure(errorMessage(issue));
    }
  }
  if (isLoading)
    return <LoadingState label="Loading application and evidence…" />;
  if (error || !application)
    return <ErrorState error={error} retry={refetch} />;
  return (
    <>
      <button
        className="text-action back-action"
        onClick={() => dispatch(caseSelected({ caseId: null }))}
      >
        ← All applications
      </button>
      <section className="case-header case-header--compact">
        <div>
          <h1>{application.business_name}</h1>
          <p>
            {application.industry} · {application.operating_months} months in
            operation
          </p>
          <p className="case-purpose">{application.purpose}</p>
        </div>
        <div className="case-header-actions">
          <div className="requested-amount">
            <span>Requested funding</span>
            <strong>{formatMoney(application.amount)}</strong>
            <small>
              {application.term_months} months ·{" "}
              {application.annual_interest_rate}% scenario rate
            </small>
          </div>
          <div className="application-review-action">
            {!runtime?.live_calls_enabled && (
              <p className="field-help">
                AI reviews are currently unavailable.
              </p>
            )}
            <Button
              disabled={busy || !runtime?.live_calls_enabled}
              onClick={beginReview}
            >
              {busy ? "Review in progress…" : "Run AI review"}
            </Button>
          </div>
        </div>
      </section>
      {failure && (
        <p role="alert" className="error-text">
          {failure}
        </p>
      )}
      <div
        className={`case-workspace ${!review ? "case-workspace--pre-review" : ""}`}
      >
        <div className="case-main">
          {review ? (
            <>
              <div className="review-selector">
                <label>
                  Review history
                  <select
                    value={review.id}
                    onChange={(event) => setChosenReview(event.target.value)}
                  >
                    {reviews.map((item) => (
                      <option key={item.id} value={item.id}>
                        {new Date(item.created_at ?? "").toLocaleString()} ·{" "}
                        {item.execution_mode} · {statusLabel(item.status ?? "")}
                      </option>
                    ))}
                  </select>
                </label>
                <span className="status-label">
                  {statusLabel(review.status ?? "")}
                </span>
              </div>
              <div className="review-metrics">
                <div>
                  <span>Processing time</span>
                  <strong>
                    {(review.processing_seconds ?? 0).toFixed(2)}s
                  </strong>
                </div>
                <div>
                  <span>Model calls</span>
                  <strong>{review.usage?.model_calls ?? 0}</strong>
                </div>
                <div>
                  <span>Estimated model cost</span>
                  <strong>
                    {review.usage?.estimated_cost_usd === null ||
                    review.usage?.estimated_cost_usd === undefined
                      ? "Not available"
                      : `$${review.usage.estimated_cost_usd.toFixed(5)}`}
                  </strong>
                </div>
              </div>
              {review.execution_mode === "offline" && (
                <p className="offline-notice">
                  OFFLINE RUN · No AI model called. These results validate the
                  workflow, not model intelligence.
                </p>
              )}
              {review.error && (
                <p className="error-text" role="alert">
                  {review.error}
                </p>
              )}
              {review.status === "interrupted" && (
                <Button
                  variant="secondary"
                  onClick={recover}
                  disabled={recovering}
                >
                  {recovering ? "Recovering…" : "Recover interrupted review"}
                </Button>
              )}
              {review.report && (
                <ReviewReportView
                  report={review.report}
                  onEvidence={setSelectedEvidence}
                />
              )}
              {review.report && (
                <HumanDecisionPanel
                  key={`${review.id}-${review.report.revision}`}
                  review={review}
                  evidenceChanged={application.version !== review.case_version}
                />
              )}
              {review.trace_url && (
                <a
                  className="trace-link"
                  href={review.trace_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Inspect this review in LangSmith ↗
                </a>
              )}
              <ReviewTimeline review={review} />
            </>
          ) : null}
        </div>
        <aside className="case-evidence">
          <EvidencePanel
            application={application}
            disabled={busy}
            selectedId={selectedEvidence}
            onSelect={setSelectedEvidence}
          />
        </aside>
      </div>
    </>
  );
}
