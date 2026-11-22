import { useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { errorMessage } from "../../components/ui/Feedback";
import { useCreateApplicationMutation } from "../../services/api/loanDeskApi";

/** Save validated application details through the API, then open its evidence workspace. */
export function CreateApplicationForm({
  onComplete,
  onCancel,
}: {
  onComplete: (id: string) => void;
  onCancel: () => void;
}) {
  const [createApplication, { isLoading }] = useCreateApplicationMutation();
  const [error, setError] = useState("");
  /** Submit declared business facts; financial evidence is attached separately, never assumed. */
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await createApplication({
        business_name: String(data.get("businessName")).trim(),
        industry: String(data.get("industry")).trim(),
        amount: String(data.get("amount")),
        purpose: String(data.get("purpose")).trim(),
        operating_months: Number(data.get("operatingMonths")),
        term_months: Number(data.get("termMonths")),
        annual_interest_rate: String(data.get("interestRate")),
        currency: "AED",
      }).unwrap();
      onComplete(result.id!);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }
  return (
    <section className="form-panel">
      <form onSubmit={submit} className="application-form">
        <label>
          Business name
          <input
            autoFocus
            name="businessName"
            required
            minLength={2}
            maxLength={120}
            placeholder="Registered business name"
          />
        </label>
        <div className="form-row">
          <label>
            Industry
            <input
              name="industry"
              required
              minLength={2}
              maxLength={80}
              placeholder="e.g. Food & beverage"
            />
          </label>
          <label>
            Months in operation
            <input
              name="operatingMonths"
              required
              type="number"
              min="0"
              max="1200"
              placeholder="36"
            />
          </label>
        </div>
        <div className="form-row">
          <label>
            Requested amount (AED)
            <input
              name="amount"
              required
              type="number"
              min="0.01"
              step="0.01"
              max="10000000"
              placeholder="150000"
            />
          </label>
          <label>
            Loan term (months)
            <input
              name="termMonths"
              required
              type="number"
              min="6"
              max="120"
              defaultValue="36"
            />
          </label>
        </div>
        <label>
          Annual interest rate for the scenario (%)
          <input
            name="interestRate"
            type="number"
            required
            min="0"
            max="50"
            step="0.01"
            defaultValue="8"
          />
        </label>
        <label>
          Purpose of funding
          <textarea
            name="purpose"
            required
            minLength={5}
            maxLength={1500}
            rows={3}
            placeholder="What will the funding help this business do?"
          />
        </label>
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
        <div className="form-actions">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={isLoading}>
            {isLoading ? "Saving…" : "Save application"}
          </Button>
        </div>
      </form>
    </section>
  );
}
