import { useEffect, useRef, useState } from "react";
import { useAppSelector } from "../../app/hooks";
import { Icon } from "../../components/ui/Icon";
import "./reviewWorkflow.css";

/** Draw directional connection routes; moving dashes illustrate flow rather than live execution. */
function FlowConnections({ join = false }: { join?: boolean }) {
  const routes = join
    ? ["M100 0 V30 H300 V80", "M300 0 V80", "M500 0 V30 H300 V80"]
    : ["M300 0 V25 H100 V80", "M300 0 V80", "M300 0 V25 H500 V80"];
  return (
    <div
      className={`workflow-connections ${join ? "workflow-connections--join" : ""}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 600 80" preserveAspectRatio="none">
        {routes.map((route) => (
          <g key={route}>
            <path className="workflow-route" d={route} />
            <path className="workflow-current" d={route} />
          </g>
        ))}
      </svg>
      <span className="workflow-flow-label">
        {join ? "Findings return" : "Review begins"}
      </span>
    </div>
  );
}

/** Explain both architectures with illustrative flow; pause motion offscreen, in hidden tabs automatically. */
export function ReviewWorkflow() {
  const multi =
    useAppSelector((state) => state.workspace.reviewMode) === "multi_agent";
  const panel = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    let inViewport = true;
    /** Run animation only when the diagram and its browser tab are visible. */
    function updateVisibility() {
      setVisible(inViewport && !document.hidden);
    }
    /** Observe viewport visibility without continuously reading layout on scroll. */
    function observeVisibility(entries: IntersectionObserverEntry[]) {
      inViewport = entries[0]?.isIntersecting ?? false;
      updateVisibility();
    }
    const observer = new IntersectionObserver(observeVisibility);
    if (panel.current) observer.observe(panel.current);
    document.addEventListener("visibilitychange", updateVisibility);
    updateVisibility();
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", updateVisibility);
    };
  }, []);
  return (
    <section
      ref={panel}
      className={`workflow-panel workflow-animated ${!visible ? "workflow-paused" : ""}`}
      aria-label={
        multi
          ? "Multi-agent review process illustration"
          : "Single-agent review process illustration"
      }
    >
      <div
        className={`workflow-diagram ${multi ? "workflow--multi" : ""}`}
        key={multi ? "multi" : "single"}
      >
        <div className="workflow-node workflow-node--lead">
          <Icon name={multi ? "workflow" : "document"} />
          <strong>{multi ? "Supervisor" : "Loan review agent"}</strong>
          <span>
            {multi
              ? "Assigns independent reviews"
              : "Investigates with shared tools"}
          </span>
        </div>
        <FlowConnections />
        <div
          className="workflow-branches"
          aria-label={
            multi
              ? "Three parallel specialist agents"
              : "Three capabilities of the same agent"
          }
        >
          {[
            ["Document checks", "document"],
            ["Financial analysis", "evaluations"],
            ["Policy checks", "approvals"],
          ].map(([label, icon]) => (
            <div className="workflow-node workflow-specialist" key={label}>
              <Icon name={icon as "document" | "evaluations" | "approvals"} />
              <strong>{label}</strong>
              <span>
                {multi
                  ? "Specialist agent · parallel review"
                  : "Shared tool · same agent"}
              </span>
            </div>
          ))}
        </div>
        <FlowConnections join />
        <div className="workflow-node workflow-node--memo">
          <Icon name="document" />
          <strong>
            {multi
              ? "Supervisor combines findings"
              : "Agent prepares the assessment"}
          </strong>
          <span>Evidence, calculations and policy in one memo</span>
        </div>
        <div className="workflow-approval-connection" aria-hidden="true">
          <span />
          <b>Pauses for your decision</b>
        </div>
        <div className="workflow-result">
          <Icon name="approvals" />
          <div>
            <strong>Human approval, always</strong>
            <span>
              A loan officer reviews the evidence and signs off on this
              assessment.
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
