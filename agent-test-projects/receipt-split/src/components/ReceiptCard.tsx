import { Link } from "react-router-dom";
import type { Receipt } from "../models";
import { formatCents } from "../utils/money";
import { StatusPill } from "./StatusPill";

interface ReceiptCardProps {
  receipt: Receipt;
}

export function ReceiptCard({ receipt }: ReceiptCardProps): React.JSX.Element {
  const paidCount = receipt.participants.filter((participant) => participant.paid).length;

  return (
    <article className="receipt-card">
      <div className="receipt-card__topline">
        <div>
          <p className="eyebrow">{new Date(`${receipt.purchasedAt}T12:00:00`).toLocaleDateString()}</p>
          <h3>{receipt.merchant}</h3>
        </div>
        <strong className="receipt-card__total">{formatCents(receipt.totalCents)}</strong>
      </div>

      <div className="receipt-card__meta">
        <StatusPill status={receipt.status} />
        <span>{receipt.items.length} items</span>
        <span>
          {paidCount}/{receipt.participants.length} paid
        </span>
      </div>

      <div className="receipt-card__actions">
        <Link className="text-link" to={`/receipts/${receipt.id}/review`}>
          Review extraction <span aria-hidden="true">→</span>
        </Link>
        <Link className="button button--secondary button--small" to={`/receipts/${receipt.id}/split`}>
          Open split
        </Link>
      </div>
    </article>
  );
}
