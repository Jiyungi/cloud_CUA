import type { InvoiceStatus } from "../models";

interface StatusBadgeProps {
  status: InvoiceStatus;
}

const LABELS: Record<InvoiceStatus, string> = {
  UPLOADED: "Uploaded",
  EXTRACTING: "Extracting",
  PENDING_REVIEW: "Needs AP review",
  PENDING_APPROVAL: "Pending approval",
  APPROVED: "Approved",
  REJECTED: "Rejected",
};

export function StatusBadge({ status }: StatusBadgeProps): React.JSX.Element {
  return <span className={`status-badge status-badge--${status.toLowerCase()}`}>{LABELS[status]}</span>;
}
