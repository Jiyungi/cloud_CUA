import type { ReceiptStatus } from "../models";

interface StatusPillProps {
  status: ReceiptStatus;
}

const LABELS: Record<ReceiptStatus, string> = {
  NEEDS_REVIEW: "Needs review",
  READY_TO_SPLIT: "Ready to split",
  PARTIALLY_PAID: "Partially paid",
  SETTLED: "Settled",
};

export function StatusPill({ status }: StatusPillProps): React.JSX.Element {
  return <span className={`status-pill status-pill--${status.toLowerCase()}`}>{LABELS[status]}</span>;
}
