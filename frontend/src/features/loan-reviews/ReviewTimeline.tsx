import { statusLabel } from "../../components/ui/Feedback";
import type { Review } from "../../types/domain";

/** Display real persisted workflow events and their measured durations, without private model reasoning. */
export function ReviewTimeline({ review }: { review: Review }) {
  return (
    <section className="timeline-panel">
      <div className="section-title">
        <h2>Review activity</h2>
        <span className="text-label">{review.review_mode}</span>
      </div>
      <ol className="event-timeline">
        {review.events?.map((event) => (
          <li key={event.id}>
            <span className="timeline-dot" />
            <div>
              <strong>
                {statusLabel(event.role)} ·{" "}
                {statusLabel(event.name.replace("agent_", ""))}
              </strong>
              <small>
                {new Date(event.at).toLocaleTimeString()}
                {event.duration_seconds !== null &&
                event.duration_seconds !== undefined
                  ? ` · ${event.duration_seconds.toFixed(3)}s`
                  : ""}
              </small>
            </div>
          </li>
        ))}
      </ol>
      {!review.events?.length && (
        <p className="muted">Waiting for the review worker.</p>
      )}
      {!!review.decisions?.length && (
        <div className="decision-history">
          <h3>Human decision history</h3>
          {review.decisions.map((decision, index) => (
            <p key={index}>
              {String(decision.reviewer)} ·{" "}
              {statusLabel(String(decision.action))} · revision{" "}
              {String(decision.revision)}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
