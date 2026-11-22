export const comparisonMetrics = [
  ["assessment_generated", "Assessments generated"],
  ["finding_precision", "Finding precision"],
  ["finding_recall", "Finding recall"],
  ["calculation_accuracy", "Tool calculation accuracy"],
  ["recommendation_accuracy", "Guardrail recommendation accuracy"],
  ["citation_validity", "Citation ID validity"],
  ["mean_seconds", "Mean processing time"],
  ["p95_seconds", "p95 processing time"],
  ["mean_cost_usd", "Mean model cost"],
] as const;

/** Keep unknown measurements distinct from zero and format each metric in its own units. */
export function metricValue(
  key: string,
  value: number | null | undefined,
): string {
  if (value == null || !Number.isFinite(value)) return "Not available";
  if (key.endsWith("seconds")) return `${value.toFixed(3)}s`;
  if (key.includes("cost")) return `$${value.toFixed(5)}`;
  return `${(value * 100).toFixed(1)}%`;
}

/** Describe the measured multi-agent change without dividing by zero or declaring an overall winner. */
export function describeDifference(
  key: string,
  single?: number | null,
  multi?: number | null,
): string {
  if (
    single == null ||
    multi == null ||
    !Number.isFinite(single) ||
    !Number.isFinite(multi)
  )
    return "Comparison unavailable";
  if (Math.abs(single - multi) < 1e-9) return "Equal measured result";
  const lowerIsBetter = key.includes("seconds") || key.includes("cost");
  if (!lowerIsBetter)
    return `Multi-agent ${multi > single ? "+" : "−"}${(Math.abs(multi - single) * 100).toFixed(1)} percentage points`;
  if (single === 0)
    return `Multi-agent ${metricValue(key, multi)}; single agent is zero`;
  return `Multi-agent ${((Math.abs(multi - single) / single) * 100).toFixed(1)}% ${multi < single ? "lower" : "higher"}`;
}
