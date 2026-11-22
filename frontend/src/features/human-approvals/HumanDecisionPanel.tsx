import { useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { errorMessage } from "../../components/ui/Feedback";
import { useSubmitDecisionMutation } from "../../services/api/loanDeskApi";
import type { HumanDecision, Review } from "../../types/domain";

/** Bind each human decision to the visible report revision and a unique idempotency key. */
export function HumanDecisionPanel({
  review,
  evidenceChanged,
}: {
  review: Review;
  evidenceChanged: boolean;
}) {
  const [submitDecision, { isLoading }] = useSubmitDecisionMutation();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const waiting =
    review.status === "awaiting_approval" ||
    review.status === "needs_information";
  if (!waiting || !review.report) return null;
  const blocking = review.status === "needs_information";
  /** Record the selected action; notes are required for revisions and cannot substitute for missing files. */
  async function decide(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    const values = new FormData(event.currentTarget);
    const action = (
      (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement
    ).value as HumanDecision["action"];
    try {
      await submitDecision({
        reviewId: review.id!,
        decision: {
          action,
          revision: review.report!.revision,
          reviewer: String(values.get("reviewer")).trim(),
          note: String(values.get("note")).trim(),
          idempotency_key: crypto.randomUUID(),
        },
      }).unwrap();
      setNotice("Decision recorded. The review is being updated.");
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }
  return (
    <section className="decision-panel">
      <span className="eyebrow">YOUR JUDGMENT MATTERS</span>
      <h2>
        {blocking ? "Resolve the evidence gaps" : "Review this assessment"}
      </h2>
      <p>
        {blocking
          ? "Attach the requested evidence, then submit an information update. A note alone cannot replace missing financial records."
          : "Check the evidence and assumptions before signing off on this exact report revision."}
      </p>
      {evidenceChanged && (
        <p className="inline-notice">
          Evidence has changed. Generate a fresh assessment before approving.
        </p>
      )}
      <form onSubmit={decide} className="decision-form">
        <label>
          Reviewer name
          <input
            name="reviewer"
            required
            minLength={2}
            maxLength={100}
            placeholder="Your name"
            autoComplete="name"
            disabled={isLoading}
          />
        </label>
        <label>
          Decision note
          <textarea
            name="note"
            maxLength={3000}
            rows={3}
            placeholder="Explain any changes, information updates or policy exceptions."
            disabled={isLoading}
          />
        </label>
        <p className="field-help">
          Local sandbox: this is an operator-entered name, not a verified bank
          identity. Signing off approves the assessment only; it does not
          approve or fund a loan.
        </p>
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        {notice && <p role="status">{notice}</p>}
        <div className="decision-actions">
          {!blocking && !evidenceChanged && (
            <Button type="submit" value="approve" disabled={isLoading}>
              Approve assessment
            </Button>
          )}
          {(blocking || evidenceChanged) && (
            <Button
              type="submit"
              value="provide_information"
              disabled={isLoading}
            >
              Submit information update
            </Button>
          )}
          <Button
            type="submit"
            value="request_changes"
            variant="secondary"
            disabled={isLoading}
          >
            Request changes
          </Button>
          <Button
            type="submit"
            value="reject"
            variant="secondary"
            disabled={isLoading}
          >
            Reject assessment
          </Button>
        </div>
      </form>
    </section>
  );
}
