import { baseApi } from "./baseApi";
import { useAppSelector } from "../../app/hooks";
import type { ReviewMode } from "../../types/reviewMode";
import type {
  ApplicationInput,
  ApplicationSummary,
  ExecutionMode,
  Experiment,
  HumanDecision,
  LoanApplication,
  Review,
  RuntimeDetails,
  SampleTemplate,
} from "../../types/domain";

type Scoped<T = void> = { reviewMode: ReviewMode; input: T };
type PollingOptions = { pollingInterval?: number };

/** Capture the active architecture for all hooks; it is part of every cache key. */
function useReviewMode(): ReviewMode {
  return useAppSelector((state) => state.workspace.reviewMode);
}

export const loanDeskApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getRuntime: build.query<RuntimeDetails, Scoped<void>>({
      query: ({ reviewMode }) => ({ reviewMode, url: "/runtime" }),
    }),
    getApplications: build.query<ApplicationSummary[], Scoped<void>>({
      query: ({ reviewMode }) => ({ reviewMode, url: "/applications" }),
      providesTags: ["Applications"],
    }),
    getApplication: build.query<LoanApplication, Scoped<string>>({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: `/applications/${input}`,
      }),
      providesTags: ["Applications"],
    }),
    getSamples: build.query<SampleTemplate[], Scoped<void>>({
      query: ({ reviewMode }) => ({ reviewMode, url: "/samples" }),
    }),
    getReviews: build.query<Review[], Scoped<string | void>>({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: `/reviews${input ? `?case_id=${input}` : ""}`,
      }),
      providesTags: ["Reviews"],
    }),
    getReview: build.query<Review, Scoped<string>>({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: `/reviews/${input}`,
      }),
      providesTags: ["Reviews"],
    }),
    getExperiments: build.query<Experiment[], Scoped<void>>({
      query: ({ reviewMode }) => ({ reviewMode, url: "/experiments" }),
      providesTags: ["Experiments"],
    }),
    createApplication: build.mutation<
      LoanApplication,
      Scoped<ApplicationInput>
    >({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: "/applications",
        method: "POST",
        body: input,
      }),
      invalidatesTags: ["Applications"],
    }),
    createSample: build.mutation<LoanApplication, Scoped<string>>({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: `/samples/${input}`,
        method: "POST",
      }),
      invalidatesTags: ["Applications"],
    }),
    uploadDocument: build.mutation<
      LoanApplication,
      Scoped<{ caseId: string; body: FormData }>
    >({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: `/applications/${input.caseId}/documents`,
        method: "POST",
        body: input.body,
      }),
      invalidatesTags: ["Applications"],
    }),
    startReview: build.mutation<
      Review,
      Scoped<{ caseId: string; executionMode: ExecutionMode }>
    >({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: `/applications/${input.caseId}/reviews`,
        method: "POST",
        body: { execution_mode: input.executionMode },
      }),
      invalidatesTags: ["Reviews", "Applications"],
    }),
    submitDecision: build.mutation<
      Review,
      Scoped<{ reviewId: string; decision: HumanDecision }>
    >({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: `/reviews/${input.reviewId}/decisions`,
        method: "POST",
        body: input.decision,
      }),
      invalidatesTags: ["Reviews", "Applications"],
    }),
    recoverReview: build.mutation<Review, Scoped<string>>({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: `/reviews/${input}/recover`,
        method: "POST",
      }),
      invalidatesTags: ["Reviews", "Applications"],
    }),
    publishExperiment: build.mutation<Experiment, Scoped<string>>({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: `/experiments/${input}/publish`,
        method: "POST",
      }),
      invalidatesTags: ["Experiments"],
    }),
    startExperiment: build.mutation<
      Experiment,
      Scoped<{ execution_mode: ExecutionMode; case_limit: number }>
    >({
      query: ({ reviewMode, input }) => ({
        reviewMode,
        url: "/experiments",
        method: "POST",
        body: input,
      }),
      invalidatesTags: ["Experiments", "Applications", "Reviews"],
    }),
  }),
});

/** Read runtime only from the selected architecture cache and API. */
export function useGetRuntimeQuery(_input?: void, options?: PollingOptions) {
  const reviewMode = useReviewMode();
  return loanDeskApi.useGetRuntimeQuery(
    { reviewMode, input: undefined },
    options,
  );
}

/** Read applications only from the selected architecture cache and API. */
export function useGetApplicationsQuery(
  _input?: void,
  options?: PollingOptions,
) {
  const reviewMode = useReviewMode();
  const scope = { reviewMode, input: undefined };
  const cached = useAppSelector(
    loanDeskApi.endpoints.getApplications.select(scope),
  );
  const active = cached.data?.some((item) =>
    ["queued", "running", "resuming"].includes(item.review_status ?? ""),
  );
  return loanDeskApi.useGetApplicationsQuery(scope, {
    ...options,
    refetchOnMountOrArgChange: true,
    pollingInterval:
      active && !cached.isError ? (options?.pollingInterval ?? 2500) : 0,
  });
}

/** Read application only from the selected architecture cache and API. */
export function useGetApplicationQuery(
  input: string,
  options?: PollingOptions,
) {
  const reviewMode = useReviewMode();
  return loanDeskApi.useGetApplicationQuery(
    { reviewMode, input: input },
    options,
  );
}

/** Read samples only from the selected architecture cache and API. */
export function useGetSamplesQuery(_input?: void, options?: PollingOptions) {
  const reviewMode = useReviewMode();
  return loanDeskApi.useGetSamplesQuery(
    { reviewMode, input: undefined },
    options,
  );
}

/** Fetch current reviews on entry; poll only active work and stop on pauses, completion or errors. */
export function useGetReviewsQuery(
  input?: string | void,
  options?: PollingOptions,
) {
  const reviewMode = useReviewMode();
  const scope = { reviewMode, input };
  const cached = useAppSelector(loanDeskApi.endpoints.getReviews.select(scope));
  const active = cached.data?.some((review) =>
    ["queued", "running", "resuming"].includes(review.status ?? ""),
  );
  return loanDeskApi.useGetReviewsQuery(scope, {
    ...options,
    pollingInterval: active && !cached.isError ? options?.pollingInterval : 0,
    refetchOnMountOrArgChange: true,
  });
}

/** Read review only from the selected architecture cache and API. */
export function useGetReviewQuery(input: string, options?: PollingOptions) {
  const reviewMode = useReviewMode();
  return loanDeskApi.useGetReviewQuery({ reviewMode, input: input }, options);
}

/** Fetch experiments on entry; poll running comparisons until completion or a request error. */
export function useGetExperimentsQuery(
  _input?: void,
  options?: PollingOptions,
) {
  const reviewMode = useReviewMode();
  const scope = { reviewMode, input: undefined };
  const cached = useAppSelector(
    loanDeskApi.endpoints.getExperiments.select(scope),
  );
  const active = cached.data?.some(
    (experiment) => experiment.status === "running",
  );
  return loanDeskApi.useGetExperimentsQuery(scope, {
    ...options,
    pollingInterval: active && !cached.isError ? options?.pollingInterval : 0,
    refetchOnMountOrArgChange: true,
  });
}

/** Bind this createApplication action to the architecture visible when its component rendered. */
export function useCreateApplicationMutation() {
  const reviewMode = useReviewMode();
  const [trigger, state] = loanDeskApi.useCreateApplicationMutation();
  return [
    (input: ApplicationInput) => trigger({ reviewMode, input }),
    state,
  ] as const;
}

/** Bind this createSample action to the architecture visible when its component rendered. */
export function useCreateSampleMutation() {
  const reviewMode = useReviewMode();
  const [trigger, state] = loanDeskApi.useCreateSampleMutation();
  return [(input: string) => trigger({ reviewMode, input }), state] as const;
}

/** Bind this uploadDocument action to the architecture visible when its component rendered. */
export function useUploadDocumentMutation() {
  const reviewMode = useReviewMode();
  const [trigger, state] = loanDeskApi.useUploadDocumentMutation();
  return [
    (input: { caseId: string; body: FormData }) =>
      trigger({ reviewMode, input }),
    state,
  ] as const;
}

/** Bind this startReview action to the architecture visible when its component rendered. */
export function useStartReviewMutation() {
  const reviewMode = useReviewMode();
  const [trigger, state] = loanDeskApi.useStartReviewMutation();
  return [
    (input: { caseId: string; executionMode: ExecutionMode }) =>
      trigger({ reviewMode, input }),
    state,
  ] as const;
}

/** Bind this submitDecision action to the architecture visible when its component rendered. */
export function useSubmitDecisionMutation() {
  const reviewMode = useReviewMode();
  const [trigger, state] = loanDeskApi.useSubmitDecisionMutation();
  return [
    (input: { reviewId: string; decision: HumanDecision }) =>
      trigger({ reviewMode, input }),
    state,
  ] as const;
}

/** Bind this recoverReview action to the architecture visible when its component rendered. */
export function useRecoverReviewMutation() {
  const reviewMode = useReviewMode();
  const [trigger, state] = loanDeskApi.useRecoverReviewMutation();
  return [(input: string) => trigger({ reviewMode, input }), state] as const;
}

/** Bind this publishExperiment action to the architecture visible when its component rendered. */
export function usePublishExperimentMutation() {
  const reviewMode = useReviewMode();
  const [trigger, state] = loanDeskApi.usePublishExperimentMutation();
  return [(input: string) => trigger({ reviewMode, input }), state] as const;
}

/** Bind this startExperiment action to the architecture visible when its component rendered. */
export function useStartExperimentMutation() {
  const reviewMode = useReviewMode();
  const [trigger, state] = loanDeskApi.useStartExperimentMutation();
  return [
    (input: { execution_mode: ExecutionMode; case_limit: number }) =>
      trigger({ reviewMode, input }),
    state,
  ] as const;
}
