import { useAppSelector } from "../../app/hooks";
import { useState } from "react";
import { Button } from "../../components/ui/Button";
import { ExportMenu } from "../../components/ui/ExportMenu";
import {
  ErrorState,
  LoadingState,
  errorMessage,
  statusLabel,
} from "../../components/ui/Feedback";
import {
  useGetExperimentsQuery,
  useGetRuntimeQuery,
  useStartExperimentMutation,
  usePublishExperimentMutation,
} from "../../services/api/loanDeskApi";
import { downloadArtifact } from "../../services/api/downloadArtifact";

import { comparisonMetrics as metrics, metricValue } from "./comparisonMetrics";
import { EvaluationComparison } from "./EvaluationComparison";

/** Run explicit paired experiments and show saved measurements with clear offline/live interpretation. */
export function EvaluationWorkspace() {
  const reviewMode = useAppSelector((state) => state.workspace.reviewMode);
  const {
    data: experiments = [],
    error,
    isLoading,
    refetch,
  } = useGetExperimentsQuery(undefined, { pollingInterval: 2500 });
  const { data: runtime } = useGetRuntimeQuery();
  const [startExperiment, { isLoading: starting }] =
    useStartExperimentMutation();
  const [publishExperiment, { isLoading: publishing }] =
    usePublishExperimentMutation();
  const [limit, setLimit] = useState(5);
  const [selectedId, setSelectedId] = useState("");
  const [failure, setFailure] = useState("");
  const selected =
    experiments.find((item) => item.id === selectedId) ?? experiments[0];
  const running = experiments.some((item) => item.status === "running");
  /** Run each selected development case through both architectures once, never auto-starting a benchmark. */
  async function start() {
    setFailure("");
    try {
      const result = await startExperiment({
        execution_mode: "live",
        case_limit: limit,
      }).unwrap();
      setSelectedId(result.id);
    } catch (issue) {
      setFailure(errorMessage(issue));
    }
  }
  /** Export the selected experiment's real rows for portfolio analysis and reproducibility. */
  async function exportResults(format: "json" | "csv") {
    if (!selected) return;
    try {
      await downloadArtifact(
        `/experiments/${selected.id}/export?format=${format}`,
        `loandesk-results.${format}`,
        reviewMode,
      );
    } catch {
      setFailure("Export could not complete. Please try again.");
    }
  }
  /** Publish saved measurements and evaluator feedback without rerunning any model call. */
  async function publish() {
    if (!selected) return;
    setFailure("");
    try {
      await publishExperiment(selected.id).unwrap();
    } catch (issue) {
      setFailure(errorMessage(issue));
    }
  }
  if (isLoading) return <LoadingState label="Loading saved experiments…" />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  return (
    <>
      <section className="benchmark-controls">
        <div className="benchmark-intro">
          <h2>Run a comparison</h2>
          <p>Compare quality, processing time and cost.</p>
        </div>
        <div className="benchmark-form">
          <label>
            <span className="sr-only">Number of cases</span>
            <select
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
              disabled={running}
            >
              {[1, 2, 3, 4, 5].map((count) => (
                <option value={count} key={count}>
                  {count} case{count > 1 ? "s" : ""} · {count * 2} reviews
                </option>
              ))}
            </select>
          </label>
          <Button
            onClick={start}
            disabled={starting || running || !runtime?.live_calls_enabled}
          >
            {starting || running
              ? "Experiment in progress…"
              : "Run paired comparison"}
          </Button>
        </div>
      </section>
      {runtime && !runtime.live_calls_enabled && (
        <p className="offline-notice">
          AI comparisons are currently unavailable. Ask the workspace
          administrator to enable them.
        </p>
      )}
      {failure && (
        <p className="error-text" role="alert">
          {failure}
        </p>
      )}
      {selected ? (
        <section className="evaluation-panel">
          <div className="panel-heading">
            <label>
              Experiment
              <select
                value={selected.id}
                onChange={(event) => setSelectedId(event.target.value)}
              >
                {experiments.map((item) => (
                  <option key={item.id} value={item.id}>
                    {new Date(item.created_at).toLocaleString()} ·{" "}
                    {item.execution_mode} · {item.status}
                  </option>
                ))}
              </select>
            </label>
            <div className="export-actions">
              {runtime?.tracing_configured &&
                selected.status === "completed" && (
                  <Button
                    variant="secondary"
                    onClick={publish}
                    disabled={publishing || selected.langsmith_published}
                  >
                    {selected.langsmith_published
                      ? "Published to LangSmith"
                      : publishing
                        ? "Publishing…"
                        : "Publish to LangSmith"}
                  </Button>
                )}
              <ExportMenu onExport={exportResults} />
            </div>
          </div>
          {selected.langsmith_dataset_url && (
            <a
              className="trace-link benchmark-context"
              href={selected.langsmith_dataset_url}
              target="_blank"
              rel="noreferrer"
            >
              Open dataset in LangSmith ↗
            </a>
          )}
          {selected.error && <p className="error-text">{selected.error}</p>}
          {Object.keys(selected.summary).length > 0 && (
            <>
              <EvaluationComparison experiment={selected} />
              <details className="benchmark-detail">
                <summary>Exact measurements in a table</summary>
                <div className="table-scroll">
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th scope="col">Measurement</th>
                        <th scope="col">Single agent</th>
                        <th scope="col">Multi-agent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.map(([key, label]) => (
                        <tr key={key}>
                          <th scope="row">{label}</th>
                          <td>
                            {metricValue(
                              key,
                              selected.summary.single_agent?.[key],
                            )}
                          </td>
                          <td>
                            {metricValue(
                              key,
                              selected.summary.multi_agent?.[key],
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </>
          )}
          <details className="benchmark-detail">
            <summary>Inspect individual case results</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Architecture</th>
                    <th>Status</th>
                    <th>Time</th>
                    <th>Finding recall</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.rows.map((row) => (
                    <tr key={row.review_id}>
                      <td>{row.sample_key}</td>
                      <td>{row.review_mode}</td>
                      <td>{statusLabel(row.status)}</td>
                      <td>{row.processing_seconds.toFixed(3)}s</td>
                      <td>
                        {metricValue(
                          "finding_recall",
                          row.scores.finding_recall,
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </section>
      ) : (
        <section className="benchmark-empty">
          <h2>No results until you run an experiment.</h2>
          <p>
            Choose how many cases to compare, then run both architectures with
            AI. API usage charges apply.
          </p>
        </section>
      )}
      <div className="evaluation-method">
        <h3>What these numbers mean</h3>
        <p>
          Finding scores evaluate agent-selected issue codes. Financial values
          and the final safety recommendation are enforced by shared
          deterministic tools. Citation validity checks document IDs, not
          whether the text fully supports a claim. Human usefulness and semantic
          grounding require separate review.
        </p>
        <p>
          No paid LLM judges run here. These five development cases are a smoke
          test, not a held-out performance benchmark. Repeated runs and a larger
          untouched test set are needed before drawing architecture conclusions.
        </p>
      </div>
    </>
  );
}
