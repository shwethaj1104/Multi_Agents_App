import { useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { errorMessage, statusLabel } from "../../components/ui/Feedback";
import { useUploadDocumentMutation } from "../../services/api/loanDeskApi";
import type { DocumentKind, LoanApplication } from "../../types/domain";

/** Attach bounded source files and let officers inspect extracted evidence without trusting document instructions. */
export function EvidencePanel({
  application,
  disabled,
  selectedId,
  onSelect,
}: {
  application: LoanApplication;
  disabled: boolean;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [uploadDocument, { isLoading }] = useUploadDocumentMutation();
  const [error, setError] = useState("");
  const [kind, setKind] = useState<DocumentKind>("profit_and_loss");
  const documents = application.documents ?? [];
  const selected = documents.find((document) => document.id === selectedId);
  /** Upload one file as multipart evidence; financial fields are validated by shared backend tools. */
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = event.currentTarget;
    const values = new FormData(form);
    const file = values.get("file");
    if (!(file instanceof File) || !file.size) {
      setError("Choose a non-empty evidence file.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Choose a file smaller than 5 MB.");
      return;
    }
    values.set("kind", kind);
    try {
      await uploadDocument({ caseId: application.id!, body: values }).unwrap();
      form.reset();
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }
  return (
    <section className="evidence-panel">
      <div className="section-title">
        <div>
          <h2>Supporting evidence</h2>
        </div>
      </div>
      <div className="evidence-list">
        {documents.length ? (
          documents.map((document) => (
            <button
              key={document.id}
              className={`evidence-item ${selectedId === document.id ? "evidence-item--selected" : ""}`}
              onClick={() =>
                onSelect(selectedId === document.id ? null : document.id!)
              }
              aria-expanded={selectedId === document.id}
            >
              <span className="file-extension">
                {document.filename.split(".").at(-1)?.toUpperCase()}
              </span>
              <span>
                <strong>{document.filename}</strong>
                <small>
                  {statusLabel(document.kind)} · {document.pages} page(s)
                </small>
              </span>
              <span aria-hidden="true">
                {selectedId === document.id ? "−" : "+"}
              </span>
            </button>
          ))
        ) : (
          <p className="muted">No evidence attached yet.</p>
        )}
      </div>
      {selected && (
        <div className="source-preview">
          <div className="section-title">
            <strong>{selected.filename}</strong>
            <Button variant="secondary" onClick={() => onSelect(null)}>
              Close
            </Button>
          </div>
          <p className="field-help">
            Extracted source text · {selected.id?.slice(0, 8)} · SHA-256{" "}
            {selected.sha256.slice(0, 12)}…
          </p>
          <pre>{selected.text}</pre>
        </div>
      )}
      <form onSubmit={upload} className="upload-form">
        <label>
          Document type
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value as DocumentKind)}
            disabled={disabled || isLoading}
          >
            <option value="profit_and_loss">Profit-and-loss statement</option>
            <option value="bank_transactions">Bank transactions</option>
            <option value="business_profile">Business profile</option>
            <option value="other">Other supporting evidence</option>
          </select>
        </label>
        <label className="file-input-label">
          Choose source file
          <input
            name="file"
            type="file"
            accept=".pdf,.csv,.json,.txt"
            required
            disabled={disabled || isLoading}
          />
        </label>
        <Button
          variant="secondary"
          type="submit"
          disabled={disabled || isLoading}
        >
          {isLoading ? "Uploading…" : "Attach evidence"}
        </Button>
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
      </form>
      <details className="evidence-format">
        <summary>File types &amp; document format</summary>
        <p>
          PDF, CSV, JSON or TXT · maximum 5 MB per file. PDFs must contain
          selectable text; scanned PDFs need text extraction first.
        </p>
        <p>
          Statement JSON or text must label <code>annual_revenue</code>,{" "}
          <code>annual_expenses</code> and <code>annual_debt_service</code>.
          Amounts are AED. Bank CSV uses <code>date,amount,category</code>;
          income rows use category <code>income</code>. Include twelve
          consecutive months.
        </p>
        <p>
          Later uploads of the same type are used for checks; earlier files
          remain in the audit trail.
        </p>
      </details>
    </section>
  );
}
