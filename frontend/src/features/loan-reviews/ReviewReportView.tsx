import { statusLabel, formatMoney } from "../../components/ui/Feedback";
import type { Report } from "../../types/domain";

/** Present authoritative checks beside the agent narrative, with source references an officer can inspect. */
export function ReviewReportView({
  report,
  onEvidence,
}: {
  report: Report;
  onEvidence: (id: string) => void;
}) {
  const values = report.financials;
  return (
    <section className="report-panel">
      <div className="section-title">
        <div>
          <span className="eyebrow">
            ASSESSMENT · REVISION {report.revision}
          </span>
          <h2>{statusLabel(report.recommendation)}</h2>
        </div>
        <span className="status-label">{report.policy_version}</span>
      </div>
      <p className="report-summary">{report.summary}</p>
      <div className="financial-grid">
        <div>
          <span>Monthly installment</span>
          <strong>{formatMoney(values.monthly_installment)}</strong>
        </div>
        <div>
          <span>Debt coverage ratio</span>
          <strong>{values.dscr ?? "Needs evidence"}</strong>
        </div>
        <div>
          <span>Annual revenue</span>
          <strong>{formatMoney(values.annual_revenue)}</strong>
        </div>
        <div>
          <span>Net operating income</span>
          <strong>{formatMoney(values.net_operating_income)}</strong>
        </div>
      </div>
      <h3>Verified checks & evidence</h3>
      <div className="findings-list">
        {report.findings.map((finding) => (
          <article className="finding" key={finding.code}>
            <div className="finding-header">
              <span className="status-label">
                {statusLabel(finding.severity)}
              </span>
              <span>
                {finding.policy_clause} · {statusLabel(finding.category)}
              </span>
            </div>
            <p>{finding.message}</p>
            <div className="source-links">
              {finding.evidence_ids?.map((id) => (
                <button key={id} onClick={() => onEvidence(id)}>
                  {report.sources.find((source) => source.id === id)
                    ?.filename ?? "Inspect source"}
                </button>
              ))}
            </div>
          </article>
        ))}
      </div>
      {report.human_note && (
        <div className="review-note">
          <h3>Human revision context</h3>
          <p>{report.human_note}</p>
        </div>
      )}
      <details className="report-limitations">
        <summary>Assumptions and limitations</summary>
        <ul>
          {report.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      </details>
    </section>
  );
}
