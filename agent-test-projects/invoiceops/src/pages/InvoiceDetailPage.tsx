import { useParams } from "react-router-dom";
import { StatusBadge } from "../components/StatusBadge";
import { useAppState } from "../state/AppStateContext";
import { formatCents } from "../utils/money";

export function InvoiceDetailPage(): React.JSX.Element {
  const { invoiceId } = useParams();
  const { invoices, loading } = useAppState();
  const invoice = invoices.find((candidate) => candidate.id === invoiceId);

  if (loading) {
    return <div className="empty-state">Loading invoice…</div>;
  }
  if (!invoice) {
    return <div className="error-state">This invoice is not visible to the active role.</div>;
  }

  return (
    <div className="page-stack">
      <header className="page-header page-header--actions">
        <div>
          <p className="eyebrow">Invoice detail</p>
          <h1>{invoice.vendorName}</h1>
          <p>
            {invoice.invoiceNumber} · {invoice.propertyName} · {invoice.workOrderNumber}
          </p>
        </div>
        <StatusBadge status={invoice.status} />
      </header>

      <div className="detail-grid">
        <section className="detail-card" aria-labelledby="extracted-fields-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Textract preview</p>
              <h2 id="extracted-fields-title">Extracted fields</h2>
            </div>
            <span>{Math.round(invoice.extractionConfidence * 100)}% confidence</span>
          </div>

          <dl className="detail-list">
            <div>
              <dt>Invoice number</dt>
              <dd>{invoice.invoiceNumber}</dd>
            </div>
            <div>
              <dt>Invoice date</dt>
              <dd>{new Date(`${invoice.invoiceDate}T12:00:00`).toLocaleDateString()}</dd>
            </div>
            <div>
              <dt>Due date</dt>
              <dd>{new Date(`${invoice.dueDate}T12:00:00`).toLocaleDateString()}</dd>
            </div>
            <div>
              <dt>Work order</dt>
              <dd>{invoice.workOrderNumber}</dd>
            </div>
          </dl>

          <div className="invoice-lines">
            {invoice.lineItems.map((line) => (
              <div key={line.id}>
                <span>{line.description}</span>
                <strong>{formatCents(line.amountCents)}</strong>
              </div>
            ))}
          </div>

          <dl className="invoice-total">
            <div>
              <dt>Subtotal</dt>
              <dd>{formatCents(invoice.subtotalCents)}</dd>
            </div>
            <div>
              <dt>Tax</dt>
              <dd>{formatCents(invoice.taxCents)}</dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd>{formatCents(invoice.totalCents)}</dd>
            </div>
          </dl>
        </section>

        <aside className="detail-stack">
          <section className="detail-card">
            <p className="eyebrow">Review note</p>
            <h2>AP context</h2>
            <p className="detail-copy">{invoice.reviewNote || "No review note has been recorded."}</p>
            <div className="decision-actions">
              <button className="button button--success button--full" type="button" disabled>
                Approve
              </button>
              <button className="button button--danger button--full" type="button" disabled>
                Reject
              </button>
            </div>
          </section>

          <section className="detail-card" aria-labelledby="audit-title">
            <p className="eyebrow">Immutable record</p>
            <h2 id="audit-title">Audit history</h2>
            <ol className="audit-list">
              {invoice.audit.map((entry) => (
                <li key={entry.id}>
                  <strong>{entry.action}</strong>
                  <span>{entry.actorName} · {new Date(entry.createdAt).toLocaleString()}</span>
                  <p>{entry.detail}</p>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </div>
  );
}
