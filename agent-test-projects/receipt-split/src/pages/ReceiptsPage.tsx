import { Link } from "react-router-dom";
import { ReceiptCard } from "../components/ReceiptCard";
import { useAppState } from "../state/AppStateContext";
import { formatCents } from "../utils/money";

export function ReceiptsPage(): React.JSX.Element {
  const { receipts, loading, error } = useAppState();
  const outstandingCents = receipts.flatMap((receipt) => receipt.participants)
    .filter((participant) => !participant.paid)
    .reduce((sum, participant) => sum + participant.amountOwedCents, 0);

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Your shared bills</p>
          <h1>Split the receipt, not the friendship.</h1>
          <p className="hero-panel__copy">
            Upload once, check the extracted items, and make every share add up exactly.
          </p>
        </div>
        <Link className="button button--primary" to="/upload">
          Add a receipt
        </Link>
      </section>

      <section className="summary-grid" aria-label="Receipt summary">
        <article className="summary-card">
          <span>Open receipts</span>
          <strong>{receipts.filter((receipt) => receipt.status !== "SETTLED").length}</strong>
        </article>
        <article className="summary-card summary-card--accent">
          <span>Still owed</span>
          <strong>{formatCents(outstandingCents)}</strong>
        </article>
      </section>

      <section aria-labelledby="recent-receipts-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Activity</p>
            <h2 id="recent-receipts-title">Recent receipts</h2>
          </div>
          <span className="section-heading__count">{receipts.length} total</span>
        </div>

        {loading ? <div className="empty-state">Loading demo receipts…</div> : null}
        {error ? <div className="error-state">{error}</div> : null}
        {!loading && !error ? (
          <div className="receipt-list">
            {receipts.map((receipt) => (
              <ReceiptCard key={receipt.id} receipt={receipt} />
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
