import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { ReviewMode } from "../types/reviewMode";
import { initialReviewMode } from "./runtimeConfiguration";

export type WorkspacePage =
  "applications" | "approvals" | "evaluations" | "workflow";
interface WorkspaceState {
  reviewMode: ReviewMode;
  page: WorkspacePage;
  activeCaseId: string | null;
  activeReviewId: string | null;
}
const initialState: WorkspaceState = {
  reviewMode: initialReviewMode(),
  page: "applications",
  activeCaseId: null,
  activeReviewId: null,
};
const workspaceSlice = createSlice({
  name: "workspace",
  initialState,
  reducers: {
    // Architecture changes close details to avoid applying a decision to the previous mode's report.
    reviewModeSelected(state, action: PayloadAction<ReviewMode>) {
      state.reviewMode = action.payload;
      state.activeCaseId = null;
      state.activeReviewId = null;
    },
    // Navigation resets detail selection; API caches remain managed independently by RTK Query.
    pageSelected(state, action: PayloadAction<WorkspacePage>) {
      state.page = action.payload;
      state.activeCaseId = null;
      state.activeReviewId = null;
    },
    // Opening a case preserves an optional report choice when arriving from the approval queue.
    caseSelected(
      state,
      action: PayloadAction<{ caseId: string | null; reviewId?: string }>,
    ) {
      state.page = "applications";
      state.activeCaseId = action.payload.caseId;
      state.activeReviewId = action.payload.reviewId ?? null;
    },
  },
});
export const { pageSelected, caseSelected, reviewModeSelected } =
  workspaceSlice.actions;
export const workspaceReducer = workspaceSlice.reducer;
