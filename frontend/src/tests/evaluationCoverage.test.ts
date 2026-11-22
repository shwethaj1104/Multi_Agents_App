import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EvaluationComparison } from "../features/evaluation-results/EvaluationComparison";
import { comparisonMetrics } from "../features/evaluation-results/comparisonMetrics";
import type { Experiment } from "../types/domain";

// Minimal offline rendering fixture; these values are never saved or displayed as benchmark results.
const experiment = {
  id: "render-test",
  execution_mode: "offline",
  summary: {
    single_agent: { mean_seconds: 0, mean_cost_usd: null },
    multi_agent: { mean_seconds: 1, mean_cost_usd: null },
  },
  rows: [],
} as unknown as Experiment;

describe("evaluation measurement coverage", () => {
  it("shows all nine measurements without a table disclosure", () => {
    const markup = renderToStaticMarkup(
      createElement(EvaluationComparison, { experiment }),
    );
    for (const [, label] of comparisonMetrics) expect(markup).toContain(label);
    expect(markup).toContain("Not available");
    expect(markup).toContain("0.000s");
    expect(markup).not.toContain("NaN");
    expect(markup).not.toContain("Infinity");
  });
});
