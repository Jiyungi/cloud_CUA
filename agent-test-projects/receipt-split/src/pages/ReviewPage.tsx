import { useParams } from "react-router-dom";
import { ReceiptReviewForm } from "../components/ReceiptReviewForm";
import { StatusPill } from "../components/StatusPill";
import { useAppState } from "../state/AppStateContext";

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

      <ReceiptReviewForm receipt={receipt} />
    </div>
  );
}
