import { useId, useRef, useState } from "react";
import { Button } from "./Button";
import "./exportMenu.css";

/** Offer CSV/JSON downloads in a native popover; selecting a format invokes the supplied export action. */
export function ExportMenu({
  onExport,
}: {
  onExport: (format: "csv" | "json") => Promise<void>;
}) {
  const id = useId();
  const menu = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  /** Close the menu before downloading and disable the trigger until the export finishes. */
  async function exportFormat(format: "csv" | "json") {
    menu.current?.hidePopover();
    setExporting(true);
    try {
      await onExport(format);
    } finally {
      setExporting(false);
    }
  }
  return (
    <div className="export-menu-shell">
      <Button
        className="export-menu-trigger"
        popoverTarget={id}
        aria-haspopup="dialog"
        disabled={exporting}
      >
        {exporting ? "Exporting…" : "Export"}
        <span className="export-menu-chevron" aria-hidden="true" />
      </Button>
      <div
        ref={menu}
        id={id}
        popover="auto"
        role="dialog"
        aria-label="Export format"
        className="export-format-menu"
      >
        <span className="export-menu-label">EXPORT AS</span>
        <button type="button" onClick={() => exportFormat("csv")}>
          <span className="export-file-icon">CSV</span>
          <span>
            <strong>CSV spreadsheet</strong>
            <small>Analyze results in Excel or Sheets</small>
          </span>
        </button>
        <button type="button" onClick={() => exportFormat("json")}>
          <span className="export-file-icon">JSON</span>
          <span>
            <strong>JSON data</strong>
            <small>Complete structured results</small>
          </span>
        </button>
      </div>
    </div>
  );
}
