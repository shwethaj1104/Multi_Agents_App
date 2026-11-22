import { Button } from "./Button";

/** Convert API errors into useful messages without displaying raw provider exceptions. */
export function errorMessage(error: unknown): string {
  if (typeof error === "object" && error && "data" in error) {
    const data = error.data;
    if (
      typeof data === "object" &&
      data &&
      "detail" in data &&
      typeof data.detail === "string"
    )
      return data.detail;
  }
  return "Unable to complete this request. Check the backend connection and try again.";
}

/** Announce in-progress work without suggesting a review has completed. */
export function LoadingState({
  label = "Loading workspace…",
}: {
  label?: string;
}) {
  return (
    <div className="loading-state" role="status">
      <span className="loading-dot" />
      {label}
    </div>
  );
}

/** Show a recoverable API failure with an explicit retry action. */
export function ErrorState({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <strong>We couldn’t load this view.</strong>
      <p>{errorMessage(error)}</p>
      {retry && (
        <Button variant="secondary" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** Format machine statuses consistently while retaining explicit text rather than color-only meaning. */
export function statusLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}

/** Format synthetic AED amounts using one currency presentation across cases and reports. */
export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "Not available";
  return new Intl.NumberFormat("en-AE", {
    style: "currency",
    currency: "AED",
    maximumFractionDigits: 2,
  }).format(Number(value));
}
