import type { PropsWithChildren } from "react";
import "./sidebar.css";
import type { ReviewMode } from "../../types/reviewMode";
import { Icon, type IconName } from "../ui/Icon";

import type { WorkspacePage } from "../../app/workspaceSlice";
export type { WorkspacePage } from "../../app/workspaceSlice";
const navigation: { id: WorkspacePage; label: string; icon: IconName }[] = [
  { id: "applications", label: "Applications", icon: "applications" },
  { id: "approvals", label: "Human approvals", icon: "approvals" },
  { id: "evaluations", label: "Evaluations", icon: "evaluations" },
  { id: "workflow", label: "Review workflow", icon: "workflow" },
];
type AppShellProps = PropsWithChildren<{
  reviewMode: ReviewMode;
  onModeChange: (mode: ReviewMode) => void;
  modeSwitchDisabled?: boolean;
  page: WorkspacePage;
  onNavigate: (page: WorkspacePage) => void;
}>;
/** Keep navigation and execution-mode identity consistent across all loan review screens. */
export function AppShell({
  reviewMode,
  onModeChange,
  modeSwitchDisabled = false,
  page,
  onNavigate,
  children,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <div className="brand-block">
          <span className="wordmark">
            LoanDesk<span className="brand-period">.</span>
          </span>
          <span className="brand-caption">Business lending workspace</span>
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav aria-label="Main navigation">
          {navigation.map((item) => (
            <button
              key={item.id}
              aria-label={item.label}
              className={`nav-item ${page === item.id ? "nav-item--active" : ""}`}
              aria-current={page === item.id ? "page" : undefined}
              onClick={() => onNavigate(item.id)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <div className="workspace-body">
        <header className="app-header">
          <div className="breadcrumb">
            Workspace <Icon name="chevron" />
            <strong>
              {navigation.find((item) => item.id === page)?.label}
            </strong>
          </div>
          <div
            className="architecture-switch"
            role="group"
            aria-label="Review architecture"
          >
            <button
              type="button"
              disabled={modeSwitchDisabled}
              aria-pressed={reviewMode === "single_agent"}
              onClick={() => onModeChange("single_agent")}
            >
              Single agent
            </button>
            <button
              type="button"
              disabled={modeSwitchDisabled}
              aria-pressed={reviewMode === "multi_agent"}
              onClick={() => onModeChange("multi_agent")}
            >
              Multi-agent
            </button>
          </div>
        </header>
        <main id="main-content" className="main-content" key={page}>
          {children}
        </main>
        <footer className="workspace-footer">
          <span>LoanDesk · Business lending</span>
          <span>No automatic lending decisions</span>
        </footer>
      </div>
    </div>
  );
}
