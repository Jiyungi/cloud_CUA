import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { InvoiceTable } from "../components/InvoiceTable";
import { MetricCard } from "../components/MetricCard";
import type { InvoiceStatus } from "../models";
import { useAppState } from "../state/AppStateContext";
import { describeDueDate } from "../utils/dates";
import { formatCents } from "../utils/money";

type StatusFilter = "ALL" | InvoiceStatus;
type DueFilter = "ALL" | "OVERDUE" | "DUE_SOON" | "LATER" | "MISSING";

export function InvoicesPage(): React.JSX.Element {
  const { invoices, currentUser, loading, error } = useAppState();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [dueFilter, setDueFilter] = useState<DueFilter>("ALL");
  const pendingReview = invoices.filter((invoice) => invoice.status === "PENDING_REVIEW");
  const pendingApproval = invoices.filter((invoice) => invoice.status === "PENDING_APPROVAL");
  const openValue = invoices
    .filter((invoice) => !["APPROVED", "REJECTED"].includes(invoice.status))
    .reduce((sum, invoice) => sum + invoice.totalCents, 0);
  const filteredInvoices = useMemo(
    () =>
      invoices.filter((invoice) => {
        if (statusFilter !== "ALL" && invoice.status !== statusFilter) {
          return false;
        }
        if (dueFilter === "ALL") {
          return true;
        }
        if (!invoice.dueDate) {
          return dueFilter === "MISSING";
        }
        const due = describeDueDate(invoice.dueDate, invoice.status);
        if (!due) {
          return dueFilter === "LATER";
        }
        if (dueFilter === "OVERDUE") {
          return due.state === "overdue";
        }
        if (dueFilter === "DUE_SOON") {
          return due.daysUntilDue >= 0 && due.daysUntilDue <= 7;
        }
        return dueFilter === "LATER" && due.daysUntilDue > 7;
      }),
    [dueFilter, invoices, statusFilter],
  );

  return (
    <div className="page-stack">
      <header className="page-header page-header--actions">
        <div>
          <p className="eyebrow">Invoice operations</p>
          <h1>Keep every invoice moving.</h1>
          <p>
            {currentUser ? `${currentUser.name} is viewing the queue as ${currentUser.role.replaceAll("_", " ")}.` : "Loading role…"}
          </p>
        </div>
        {currentUser?.role === "vendor" ? (
          <Link className="button button--primary" to="/upload">
            Upload invoice
          </Link>
        ) : null}
      </header>

      <section className="metrics-grid" aria-label="Invoice summary">
        <MetricCard label="Needs AP review" value={String(pendingReview.length)} detail="Extracted fields need confirmation" tone="warning" />
        <MetricCard label="Awaiting approval" value={String(pendingApproval.length)} detail="Assigned property-manager decisions" />
        <MetricCard label="Open value" value={formatCents(openValue)} detail="Visible to the active fixture role" tone="success" />
      </section>

      <section aria-labelledby="invoice-queue-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Visible workload</p>
            <h2 id="invoice-queue-title">Invoice queue</h2>
          </div>
          <span>
            {filteredInvoices.length} of {invoices.length} records
          </span>
        </div>

        <div className="queue-filters" role="group" aria-label="Invoice queue filters">
          <label>
            Status
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
              <option value="ALL">All statuses</option>
              <option value="UPLOADED">Uploaded</option>
              <option value="EXTRACTING">Extracting</option>
              <option value="PENDING_REVIEW">Pending review</option>
              <option value="PENDING_APPROVAL">Pending approval</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </label>
          <label>
            Due date
            <select value={dueFilter} onChange={(event) => setDueFilter(event.target.value as DueFilter)}>
              <option value="ALL">All due dates</option>
              <option value="OVERDUE">Overdue</option>
              <option value="DUE_SOON">Due within 7 days</option>
              <option value="LATER">Later or closed</option>
              <option value="MISSING">Not extracted</option>
            </select>
          </label>
        </div>

        {loading ? <div className="empty-state">Loading demo invoices…</div> : null}
        {error ? <div className="error-state" role="alert">{error}</div> : null}
        {!loading && !error ? (
          <InvoiceTable invoices={filteredInvoices} emptyMessage="No invoices match these filters for the active role." />
        ) : null}
      </section>
    </div>
  );
}
