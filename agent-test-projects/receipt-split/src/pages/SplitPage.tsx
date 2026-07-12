import { useParams } from "react-router-dom";
import { SplitEditor } from "../components/SplitEditor";
import { useAppState } from "../state/AppStateContext";

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

  return (
    <div className="page-stack page-stack--narrow">
      <header className="page-header">
        <p className="eyebrow">Split summary</p>
        <h1>{receipt.merchant}</h1>
        <p>Every share is shown in cents-backed totals so the split stays exact.</p>
      </header>

      <SplitEditor receipt={receipt} />
    </div>
  );
}
