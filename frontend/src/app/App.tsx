import { useState, type FormEvent } from "react";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/Button";
import { ErrorState, LoadingState } from "../components/ui/Feedback";
import { ApplicationsWorkspace } from "../features/loan-applications/ApplicationsWorkspace";
import { ApplicationDetail } from "../features/loan-applications/ApplicationDetail";
import { CreateApplicationForm } from "../features/loan-applications/CreateApplicationForm";
import { ApprovalQueue } from "../features/human-approvals/ApprovalQueue";
import { EvaluationWorkspace } from "../features/evaluation-results/EvaluationWorkspace";
import { ReviewWorkflow } from "../features/loan-reviews/ReviewWorkflow";
import { useGetRuntimeQuery } from "../services/api/loanDeskApi";
import { useAppDispatch, useAppSelector } from "./hooks";
import {
  caseSelected,
  pageSelected,
  reviewModeSelected,
  type WorkspacePage,
} from "./workspaceSlice";
import type { ReviewMode } from "../types/reviewMode";

/** Compose a business review workspace with explicit offline/live identity and reusable feature views. */
export function App() {
  const dispatch = useAppDispatch();
  const { page, activeCaseId, reviewMode } = useAppSelector(
    (state) => state.workspace,
  );
  const {
    currentData: runtime,
    error,
    isFetching,
    refetch,
  } = useGetRuntimeQuery();
  const [creating, setCreating] = useState(false);
  const submitting = useAppSelector((state) =>
    Object.values(state.loanDeskApi.mutations).some(
      (mutation) => mutation?.status === "pending",
    ),
  );
  const multi = reviewMode === "multi_agent";
  const headings = {
    applications: "Applications",
    approvals: "Human approvals",
    evaluations: "Eval matrix",
    workflow: "Review workflow",
  };
  /** Switch product sections without retaining a stale case or pending creation form. */
  function navigate(next: WorkspacePage) {
    dispatch(pageSelected(next));
    setCreating(false);
  }
  /** Change architecture without carrying active reports or unsaved forms into the other mode. */
  function switchMode(mode: ReviewMode) {
    if (mode === reviewMode) return;
    setCreating(false);
    dispatch(reviewModeSelected(mode));
    try {
      localStorage.setItem("loandesk_review_mode", mode);
    } catch {
      /* Switching still works if preference storage is unavailable. */
    }
  }
  /** Store only a workspace-access credential in session storage when protected local hosting is configured. */
  function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sessionStorage.setItem(
      "loandesk_workspace_token",
      String(new FormData(event.currentTarget).get("token")).trim(),
    );
    void refetch();
  }
  const unauthorized =
    typeof error === "object" &&
    error &&
    "status" in error &&
    error.status === 401;
  return (
    <AppShell
      key={reviewMode}
      reviewMode={reviewMode}
      onModeChange={switchMode}
      modeSwitchDisabled={submitting}
      page={page}
      onNavigate={navigate}
    >
      {isFetching && !runtime ? (
        <LoadingState />
      ) : unauthorized ? (
        <section className="form-panel">
          <h1>Connect to this workspace</h1>
          <p>This server requires its workspace access token.</p>
          <form onSubmit={connect} className="application-form">
            <label>
              Workspace token
              <input type="password" name="token" required autoComplete="off" />
            </label>
            <Button type="submit">Connect</Button>
          </form>
        </section>
      ) : error ? (
        <ErrorState error={error} retry={refetch} />
      ) : runtime?.review_mode !== reviewMode ? (
        <div className="error-state" role="alert">
          The frontend and API architecture modes do not match. Start the
          matching backend on port {multi ? "8012" : "8011"}.
        </div>
      ) : (
        <>
          {page === "applications" && activeCaseId ? (
            <ApplicationDetail key={activeCaseId} caseId={activeCaseId} />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <h1>{creating ? "New application" : headings[page]}</h1>
                  {!(page === "applications" && creating) && (
                    <p className="page-description">
                      {page === "applications"
                        ? "From supporting evidence to a considered human decision."
                        : page === "approvals"
                          ? "Inspect the assessment. Resolve questions. Make the final call."
                          : page === "evaluations"
                            ? "The same cases, tools and policy. A fair comparison."
                            : multi
                              ? "Three specialists review in parallel. One supervisor brings their findings together for your decision."
                              : "One agent reviews documents, finances and policy to prepare an assessment for your decision."}
                    </p>
                  )}
                </div>
              </div>
              {page === "applications" &&
                (creating ? (
                  <CreateApplicationForm
                    onCancel={() => setCreating(false)}
                    onComplete={(id) => {
                      setCreating(false);
                      dispatch(caseSelected({ caseId: id }));
                    }}
                  />
                ) : (
                  <ApplicationsWorkspace onCreate={() => setCreating(true)} />
                ))}
              {page === "approvals" && <ApprovalQueue />}
              {page === "evaluations" && <EvaluationWorkspace />}
              {page === "workflow" && <ReviewWorkflow />}
            </>
          )}
        </>
      )}
    </AppShell>
  );
}
