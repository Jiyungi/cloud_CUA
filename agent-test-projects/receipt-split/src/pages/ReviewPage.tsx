import { Link, useParams } from "react-router-dom";
import { StatusPill } from "../components/StatusPill";
import { useAppState } from "../state/AppStateContext";
import { formatCents } from "../utils/money";

export function ReviewPage(): React.JSX.Element {
  const { receiptId } = useParams();
  const { receipts, loading } = useAppState();
  const receipt = receipts.find((candidate) => candidate.id === receiptId);

  if (loading) {
    return <div className="empty-state">Loading extraction…</div>;
  }

  if (!receipt) {
    return <div className="error-state">This receipt could not be found.</div>;
  }

  return (
    <div className="page-stack page-stack--narrow">
      <header className="page-header page-header--split">
        <div>
          <p className="eyebrow">Extraction review</p>
          <h1>{receipt.merchant}</h1>
          <p>Review the extracted fields before confirming the amount to split.</p>
        </div>
        <StatusPill status={receipt.status} />
      </header>

      <section className="form-card">
        <div className="field-grid">
          <label>
            Merchant
            <input defaultValue={receipt.merchant} readOnly />
          </label>
          <label>
            Purchase date
            <input defaultValue={receipt.purchasedAt} readOnly type="date" />
          </label>
        </div>

        <div className="line-items" aria-labelledby="line-items-title">
          <div className="section-heading section-heading--compact">
            <h2 id="line-items-title">Line items</h2>
            <span>{Math.round(receipt.extractionConfidence * 100)}% confidence</span>
          </div>
          {receipt.items.map((item) => (
            <div className="line-item" key={item.id}>
              <div>
                <strong>{item.name}</strong>
                <span>Qty {item.quantity}</span>
              </div>
              <strong>{formatCents(item.amountCents)}</strong>
            </div>
          ))}
        </div>

        <dl className="totals-list">
          <div>
            <dt>Subtotal</dt>
            <dd>{formatCents(receipt.subtotalCents)}</dd>
          </div>
          <div>
            <dt>Tax</dt>
            <dd>{formatCents(receipt.taxCents)}</dd>
          </div>
          <div>
            <dt>Tip</dt>
            <dd>{formatCents(receipt.tipCents)}</dd>
          </div>
          <div className="totals-list__total">
            <dt>Total</dt>
            <dd>{formatCents(receipt.totalCents)}</dd>
          </div>
        </dl>

        <Link className="button button--primary button--full" to={`/receipts/${receipt.id}/split`}>
          Continue to split
        </Link>
      </section>
    </div>
  );
}
