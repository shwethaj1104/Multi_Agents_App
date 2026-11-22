import { configureStore } from "@reduxjs/toolkit";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { baseApi } from "../services/api/baseApi";
import { loanDeskApi } from "../services/api/loanDeskApi";
import {
  workspaceReducer,
  caseSelected,
  reviewModeSelected,
} from "../app/workspaceSlice";

/** Create an isolated Redux/API store; tests never contact a backend or a model provider. */
function testStore() {
  return configureStore({
    reducer: {
      workspace: workspaceReducer,
      [baseApi.reducerPath]: baseApi.reducer,
    },
    middleware: (defaults) => defaults().concat(baseApi.middleware),
  });
}

beforeEach(() => {
  vi.stubEnv("VITE_SINGLE_AGENT_API_BASE_URL", "http://single.test/api/v1");
  vi.stubEnv("VITE_MULTI_AGENT_API_BASE_URL", "http://multi.test/api/v1");
  vi.stubGlobal("sessionStorage", { getItem: () => null });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("one UI architecture routing", () => {
  it("clears selected reports while preserving the selected architecture", () => {
    const store = testStore();
    store.dispatch(
      caseSelected({ caseId: "case-1", reviewId: "report-single" }),
    );
    store.dispatch(reviewModeSelected("multi_agent"));
    expect(store.getState().workspace).toMatchObject({
      reviewMode: "multi_agent",
      activeCaseId: null,
      activeReviewId: null,
    });
  });

  it("keeps identical endpoint arguments in separate per-mode caches", async () => {
    const requests: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        requests.push(request.url);
        return Response.json({
          review_mode: request.url.includes("single.test")
            ? "single_agent"
            : "multi_agent",
        });
      }),
    );
    const store = testStore();
    const single = { reviewMode: "single_agent", input: undefined } as const;
    const multi = { reviewMode: "multi_agent", input: undefined } as const;
    const first = store.dispatch(
      loanDeskApi.endpoints.getRuntime.initiate(single),
    );
    expect((await first.unwrap()).review_mode).toBe("single_agent");
    store.dispatch(reviewModeSelected("multi_agent"));
    const second = store.dispatch(
      loanDeskApi.endpoints.getRuntime.initiate(multi),
    );
    expect((await second.unwrap()).review_mode).toBe("multi_agent");
    expect(
      loanDeskApi.endpoints.getRuntime.select(single)(store.getState()).data
        ?.review_mode,
    ).toBe("single_agent");
    expect(
      loanDeskApi.endpoints.getRuntime.select(multi)(store.getState()).data
        ?.review_mode,
    ).toBe("multi_agent");
    expect(requests).toEqual([
      "http://single.test/api/v1/runtime",
      "http://multi.test/api/v1/runtime",
    ]);
    first.unsubscribe();
    second.unsubscribe();
    store.dispatch(baseApi.util.resetApiState());
  });

  it("does not let a late previous-mode response replace the current-mode cache", async () => {
    let releaseSingle: (() => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        if (request.url.includes("single.test"))
          await new Promise<void>((resolve) => {
            releaseSingle = resolve;
          });
        return Response.json({
          review_mode: request.url.includes("single.test")
            ? "single_agent"
            : "multi_agent",
        });
      }),
    );
    const store = testStore();
    const first = store.dispatch(
      loanDeskApi.endpoints.getRuntime.initiate({
        reviewMode: "single_agent",
        input: undefined,
      }),
    );
    await vi.waitFor(() => expect(releaseSingle).toBeDefined());
    store.dispatch(reviewModeSelected("multi_agent"));
    const multi = { reviewMode: "multi_agent", input: undefined } as const;
    const second = store.dispatch(
      loanDeskApi.endpoints.getRuntime.initiate(multi),
    );
    await second.unwrap();
    releaseSingle!();
    await first.unwrap();
    expect(
      loanDeskApi.endpoints.getRuntime.select(multi)(store.getState()).data
        ?.review_mode,
    ).toBe("multi_agent");
    first.unsubscribe();
    second.unsubscribe();
    store.dispatch(baseApi.util.resetApiState());
  });

  it("routes review creation and human decisions to their explicitly captured architecture", async () => {
    const requests: { url: string; body: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        requests.push({ url: request.url, body: await request.json() });
        return Response.json({ id: "review-1" });
      }),
    );
    const store = testStore();
    await store
      .dispatch(
        loanDeskApi.endpoints.startReview.initiate({
          reviewMode: "single_agent",
          input: { caseId: "case-1", executionMode: "offline" },
        }),
      )
      .unwrap();
    store.dispatch(reviewModeSelected("multi_agent"));
    await store
      .dispatch(
        loanDeskApi.endpoints.submitDecision.initiate({
          reviewMode: "single_agent",
          input: {
            reviewId: "review-1",
            decision: {
              action: "reject",
              revision: 1,
              reviewer: "Test officer",
              note: "Test",
              idempotency_key: "test-decision",
            },
          },
        }),
      )
      .unwrap();
    expect(requests[0].url).toBe(
      "http://single.test/api/v1/applications/case-1/reviews",
    );
    expect(requests[1].url).toBe(
      "http://single.test/api/v1/reviews/review-1/decisions",
    );
    expect(requests[0].body).toEqual({ execution_mode: "offline" });
    store.dispatch(baseApi.util.resetApiState());
  });
});
