import type { Experiment } from "../../types/domain";
import {
  comparisonMetrics,
  describeDifference,
  metricValue,
} from "./comparisonMetrics";
import "./evaluationComparison.css";

type Props = { experiment: Experiment };
const modes = [
  ["single_agent", "Single agent", "S"],
  ["multi_agent", "Multi-agent", "M"],
] as const;

/** Display explicitly labeled marker shapes so architecture is never conveyed by color alone. */
function Legend() {
  return (
    <div className="ev-legend ev-legend--orbits">
      {modes.map(([mode, label, letter]) => (
        <span key={mode}>
          <i className={`ev-marker ${mode}`}>{letter}</i>
          {label}
        </span>
      ))}
    </div>
  );
}

/** Compare every requested metric in its own units; bars use shared per-metric scales, never invented scores. */
function MeasurementCards({
  experiment,
  resourcesOnly = false,
}: {
  experiment: Experiment;
  resourcesOnly?: boolean;
}) {
  const metrics = resourcesOnly
    ? comparisonMetrics.slice(6)
    : comparisonMetrics;
  return (
    <section
      className="ev-measurements"
      aria-label={
        resourcesOnly ? "Time and model cost" : "All nine measurements"
      }
    >
      <div className="ev-measurements-heading">
        <h4>
          {resourcesOnly ? "Time & model cost" : "Complete measurement summary"}
        </h4>
        <p>
          {resourcesOnly
            ? "Three resource measurements · lower is better"
            : "All nine measurements across both architectures"}
        </p>
      </div>
      <div className="ev-measurement-grid">
        {metrics.map(([key, label]) => {
          const resource = key.includes("seconds") || key.includes("cost");
          const values = modes.map(([mode]) => experiment.summary[mode]?.[key]);
          const maximum = resource
            ? Math.max(
                ...values.filter(
                  (value): value is number =>
                    value != null && Number.isFinite(value),
                ),
                0,
              )
            : 1;
          return (
            <article className="ev-measurement-card" key={key}>
              <h4>{label}</h4>
              <span className="ev-metric-direction">
                {resource ? "Lower is better" : "Higher is better"}
              </span>
              {modes.map(([mode, name], index) => {
                const value = values[index];
                const known = value != null && Number.isFinite(value);
                const width =
                  known && maximum > 0
                    ? Math.max(0, Math.min(100, (value / maximum) * 100))
                    : 0;
                return (
                  <div className="ev-metric-row" key={mode}>
                    <div>
                      <span>{name}</span>
                      <strong>{metricValue(key, value)}</strong>
                    </div>
                    <div className="ev-metric-track" aria-hidden="true">
                      {known && (
                        <span className={mode} style={{ width: `${width}%` }} />
                      )}
                    </div>
                  </div>
                );
              })}
              <p>{describeDifference(key, values[0], values[1])}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

/** Show six independent quality signals as paired rings; no invented aggregate quality score. */
function QualityOrbits({ experiment }: Props) {
  return (
    <>
      <div className="ev-orbits">
        {comparisonMetrics.slice(0, 6).map(([key, label]) => (
          <article className="ev-orbit" key={key}>
            <div className="ev-ring">
              <svg viewBox="0 0 140 140" aria-hidden="true">
                {modes.map(([mode], i) => {
                  const value = experiment.summary[mode]?.[key];
                  const r = i ? 43 : 57;
                  const circumference = 2 * Math.PI * r;
                  return (
                    <g key={mode}>
                      <circle className="ev-ring-track" cx="70" cy="70" r={r} />
                      {value != null && Number.isFinite(value) && (
                        <circle
                          className={`ev-ring-value ${mode}`}
                          cx="70"
                          cy="70"
                          r={r}
                          strokeDasharray={`${Math.max(0, Math.min(1, value)) * circumference} ${circumference}`}
                        />
                      )}
                    </g>
                  );
                })}
              </svg>
              <span>S / M</span>
            </div>
            <h4>{label}</h4>
            <div className="ev-values">
              {modes.map(([mode, , letter]) => (
                <span key={mode}>
                  {letter} · {metricValue(key, experiment.summary[mode]?.[key])}
                </span>
              ))}
            </div>
            <p>
              {describeDifference(
                key,
                experiment.summary.single_agent?.[key],
                experiment.summary.multi_agent?.[key],
              )}
            </p>
          </article>
        ))}
      </div>
      <MeasurementCards experiment={experiment} resourcesOnly />
    </>
  );
}

/** Present six quality rings and three resource measurements from the saved experiment. */
export function EvaluationComparison({ experiment }: Props) {
  return (
    <section className="ev-comparison" aria-label="Architecture comparison">
      <header className="ev-view-heading">
        <div className="ev-results-heading">
          <h3>
            {experiment.execution_mode === "offline"
              ? "OFFLINE WORKFLOW MEASUREMENTS"
              : "MEASURED MODEL RESULTS"}
          </h3>
          <p>
            Every ring uses a 0–100% scale. Empty rings with “Not available”
            have no measurement.
          </p>
        </div>
        <Legend />
      </header>
      <div className="ev-view-enter" key={experiment.id}>
        <QualityOrbits experiment={experiment} />
      </div>
    </section>
  );
}
