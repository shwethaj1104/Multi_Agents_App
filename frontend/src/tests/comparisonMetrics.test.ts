import { describe, expect, it } from "vitest";
import { describeDifference, metricValue } from "../features/evaluation-results/comparisonMetrics";

describe("honest evaluation comparisons", () => {
  it("distinguishes missing values, zero and ties", () => {
    expect(metricValue("mean_cost_usd", null)).toBe("Not available");
    expect(metricValue("mean_cost_usd", 0)).toBe("$0.00000");
    expect(describeDifference("finding_recall", 1, 1)).toBe("Equal measured result");
    expect(describeDifference("mean_seconds", 0, 1)).not.toContain("Infinity");
    expect(describeDifference("mean_seconds", null, 1)).toBe("Comparison unavailable");
  });
  it("uses percentage points for quality and relative differences for resources", () => {
    expect(describeDifference("finding_recall", .8, .9)).toBe("Multi-agent +10.0 percentage points");
    expect(describeDifference("mean_seconds", 10, 5)).toBe("Multi-agent 50.0% lower");
    expect(describeDifference("mean_cost_usd", .01, .02)).toBe("Multi-agent 100.0% higher");
  });
});
