import { useState } from "react";
import type { Invoice } from "../models";
import { useAppState } from "../state/AppStateContext";

interface DecisionPanelProps {
  invoice: Invoice;
}

export function DecisionPanel({ invoice }: DecisionPanelProps): React.JSX.Element {
  const { api, refresh } = useAppState();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: "APPROVED" | "REJECTED"): Promise<void> {
    if (reason.trim().length < 5) {
      setError("Enter a clear reason before approving or rejecting this invoice.");
      return;
    }

    try {
      setBusy(true);
      setError(null);
      await api.decideInvoice(invoice.id, { decision, reason });
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The decision could not be recorded.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="decision-panel">
      <label className="stacked-field" htmlFor="decision-reason">
        Decision reason
        <textarea
          id="decision-reason"
          rows={4}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Explain the approval or what the vendor must correct."
        />
      </label>
      {error ? (
        <div className="inline-error" role="alert">
          {error}
        </div>
      ) : null}
      <div className="decision-actions">
        <button className="button button--success button--full" type="button" disabled={busy} onClick={() => void decide("APPROVED")}>
          Approve
        </button>
        <button className="button button--danger button--full" type="button" disabled={busy} onClick={() => void decide("REJECTED")}>
          Reject
        </button>
      </div>
    </div>
  );
}
