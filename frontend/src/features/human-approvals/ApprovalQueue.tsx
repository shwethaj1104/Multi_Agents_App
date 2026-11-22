import { useAppDispatch } from "../../app/hooks";
import { caseSelected } from "../../app/workspaceSlice";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import {
  ErrorState,
  LoadingState,
  statusLabel,
} from "../../components/ui/Feedback";
import {
  useGetApplicationsQuery,
  useGetReviewsQuery,
} from "../../services/api/loanDeskApi";

/** Show real paused assessments and take the officer to the exact report that needs a decision. */
export function ApprovalQueue() {
  const dispatch = useAppDispatch();
  const {
    data: reviews = [],
    error,
    isLoading,
    refetch,
  } = useGetReviewsQuery(undefined, { pollingInterval: 3000 });
  const { data: cases = [] } = useGetApplicationsQuery();
  const waiting = reviews.filter((review) =>
    ["awaiting_approval", "needs_information", "interrupted"].includes(
      review.status ?? "",
    ),
  );
  if (isLoading) return <LoadingState label="Loading the review queue…" />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  if (!waiting.length)
    return (
      <EmptyState
        icon="approvals"
        title="Nothing awaiting your decision"
        description="Start a review from an application. Its assessment will pause here before any human sign-off."
      />
    );
  return (
    <section className="approval-list">
      {waiting.map((review) => (
        <article className="approval-card" key={review.id}>
          <div>
            <span className="eyebrow">
              {review.execution_mode?.toUpperCase()} · REVISION{" "}
              {review.report?.revision ?? "—"}
            </span>
            <h2>
              {cases.find((item) => item.id === review.case_id)
                ?.business_name ?? "Business application"}
            </h2>
            <p>
              {review.status === "needs_information"
                ? "Supporting information is required before sign-off."
                : review.status === "interrupted"
                  ? "Interrupted work can be explicitly recovered."
                  : "The evidence-backed assessment is ready for your review."}
            </p>
            <span className="status-label">
              {statusLabel(review.status ?? "")}
            </span>
          </div>
          <Button
            variant="secondary"
            onClick={() =>
              dispatch(
                caseSelected({ caseId: review.case_id, reviewId: review.id }),
              )
            }
          >
            Inspect assessment
          </Button>
        </article>
      ))}
    </section>
  );
}
