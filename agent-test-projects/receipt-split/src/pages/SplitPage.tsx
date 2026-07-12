import { Link, useParams } from "react-router-dom";
import { useAppState } from "../state/AppStateContext";
import { formatCents } from "../utils/money";

export function SplitPage(): React.JSX.Element {
  const { receiptId } = useParams();
  const { receipts, loading } = useAppState();
  const receipt = receipts.find((candidate) => candidate.id === receiptId);

  if (loading) {
    return <div className="empty-state">Loading split…</div>;
  }

  if (!receipt) {
    return <div className="error-state">This split could not be found.</div>;
  }

  const allocatedCents = receipt.participants.reduce(
    (sum, participant) => sum + participant.amountOwedCents,
    0,
  );

  return (
    <div className="page-stack page-stack--narrow">
      <header className="page-header">
        <p className="eyebrow">Split summary</p>
        <h1>{receipt.merchant}</h1>
        <p>Every share is shown in cents-backed totals so the split stays exact.</p>
      </header>

      <section className="split-total">
        <span>Receipt total</span>
        <strong>{formatCents(receipt.totalCents)}</strong>
        <div className="allocation-meter" aria-label={`${formatCents(allocatedCents)} allocated`}>
          <span style={{ width: `${Math.min((allocatedCents / receipt.totalCents) * 100, 100)}%` }} />
        </div>
        <small>{formatCents(allocatedCents)} allocated</small>
      </section>

      <section aria-labelledby="friends-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Friends</p>
            <h2 id="friends-title">Who owes what</h2>
          </div>
          <button className="text-button" type="button" disabled title="Friend editing is added in the next fixture milestone">
            Add friend
          </button>
        </div>

        <div className="participant-list">
          {receipt.participants.map((participant) => (
            <article className="participant-card" key={participant.id}>
              <span className="participant-card__avatar" aria-hidden="true">
                {participant.name.slice(0, 1)}
              </span>
              <div className="participant-card__identity">
                <strong>{participant.name}</strong>
                <span>{participant.paid ? "Paid" : "Waiting"}</span>
              </div>
              <strong>{formatCents(participant.amountOwedCents)}</strong>
            </article>
          ))}
        </div>
      </section>

      <div className="action-stack">
        <button
          className="button button--primary button--full"
          type="button"
          disabled
          title="Split editing is added in the next fixture milestone"
        >
          Save split
        </button>
        <Link className="button button--ghost button--full" to="/receipts">
          Back to receipts
        </Link>
      </div>
    </div>
  );
}
