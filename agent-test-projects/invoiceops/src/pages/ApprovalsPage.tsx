import { InvoiceTable } from "../components/InvoiceTable";
import { useAppState } from "../state/AppStateContext";

export function ApprovalsPage(): React.JSX.Element {
  const { invoices, currentUser, loading } = useAppState();
  const pending = invoices.filter((invoice) => invoice.status === "PENDING_APPROVAL");

  return (
    <div className="page-stack">
      <header className="page-header">
        <p className="eyebrow">Human decision queue</p>
        <h1>Approvals</h1>
        <p>
          The future AWS workflow will pause in Step Functions until the assigned property manager makes a decision.
        </p>
      </header>

      <section aria-labelledby="pending-approvals-title">
        <div className="section-heading">
          <div>
            <h2 id="pending-approvals-title">Pending for {currentUser?.name ?? "this role"}</h2>
          </div>
          <span>{pending.length} waiting</span>
        </div>
        {loading ? (
          <div className="empty-state">Loading approvals…</div>
        ) : (
          <InvoiceTable invoices={pending} emptyMessage="No pending approvals are assigned to this role." />
        )}
      </section>
    </div>
  );
}
