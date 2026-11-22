import type { ReviewMode } from "../../types/reviewMode";
import { reviewApiBaseUrl } from "../../app/runtimeConfiguration";

/** Download an authenticated API artifact without putting credentials in a URL or Redux state. */
export async function downloadArtifact(
  path: string,
  filename: string,
  reviewMode: ReviewMode,
): Promise<void> {
  const token = sessionStorage.getItem("loandesk_workspace_token");
  const response = await fetch(`${reviewApiBaseUrl(reviewMode)}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok)
    throw new Error("Unable to download the requested artifact.");
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
