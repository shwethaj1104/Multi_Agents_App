import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";
import type { ReviewMode } from "../../types/reviewMode";
import { reviewApiBaseUrl } from "../../app/runtimeConfiguration";

export type ModeRequest = FetchArgs & { reviewMode: ReviewMode };
const executeRequest = fetchBaseQuery({
  // Workspace tokens are browser-session credentials, never provider or database keys.
  prepareHeaders(headers) {
    const token = sessionStorage.getItem("loandesk_workspace_token");
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return headers;
  },
});

/** Route using the mode captured in this request, never a later mutable UI selection. */
const modeAwareBaseQuery: BaseQueryFn<
  ModeRequest,
  unknown,
  FetchBaseQueryError
> = (request, api, options) => {
  const { reviewMode, ...args } = request;
  return executeRequest(
    { ...args, url: `${reviewApiBaseUrl(reviewMode)}${args.url}` },
    api,
    options,
  );
};

export const baseApi = createApi({
  reducerPath: "loanDeskApi",
  baseQuery: modeAwareBaseQuery,
  tagTypes: ["Applications", "Reviews", "Experiments"],
  endpoints: () => ({}),
});
