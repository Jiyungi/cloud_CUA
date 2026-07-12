import { Link } from "react-router-dom";
import { InvoiceTable } from "../components/InvoiceTable";
import { MetricCard } from "../components/MetricCard";
import { useAppState } from "../state/AppStateContext";
import { formatCents } from "../utils/money";

export function InvoicesPage(): React.JSX.Element {
  const { invoices, currentUser, loading, error } = useAppState();
  const pendingReview = invoices.filter((invoice) => invoice.status === "PENDING_REVIEW");
  const pendingApproval = invoices.filter((invoice) => invoice.status === "PENDING_APPROVAL");
  const openValue = invoices
    .filter((invoice) => !["APPROVED", "REJECTED"].includes(invoice.status))
    .reduce((sum, invoice) => sum + invoice.totalCents, 0);

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
        <Link className="button button--primary" to="/upload">
          Upload invoice
        </Link>
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
          <span>{invoices.length} records</span>
        </div>

        {loading ? <div className="empty-state">Loading demo invoices…</div> : null}
        {error ? <div className="error-state" role="alert">{error}</div> : null}
        {!loading && !error ? (
          <InvoiceTable invoices={invoices} emptyMessage="No invoices are visible to this role." />
        ) : null}
      </section>
    </div>
  );
}
