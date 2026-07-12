import { useParams } from "react-router-dom";
import { DecisionPanel } from "../components/DecisionPanel";
import { DueDateFlag } from "../components/DueDateFlag";
import { InvoiceReviewForm } from "../components/InvoiceReviewForm";
import { StatusBadge } from "../components/StatusBadge";
import { useAppState } from "../state/AppStateContext";
import { formatDateOnly } from "../utils/dates";
import { formatCents } from "../utils/money";

export function InvoiceDetailPage(): React.JSX.Element {
  const { invoiceId } = useParams();
  const { invoices, currentUser, loading } = useAppState();
  const invoice = invoices.find((candidate) => candidate.id === invoiceId);

  if (loading) {
    return <div className="empty-state">Loading invoice…</div>;
  }
  if (!invoice) {
    return <div className="error-state">This invoice is not visible to the active role.</div>;
  }

  const canReview = invoice.status === "PENDING_REVIEW" && currentUser?.role === "ap_clerk";
  const canDecide =
    invoice.status === "PENDING_APPROVAL" &&
    currentUser?.role === "property_manager" &&
    currentUser.id === invoice.assignedManagerId;

  return (
    <div className="page-stack">
      <header className="page-header page-header--actions detail-header">
        <div>
          <p className="eyebrow">Invoice detail</p>
          <h1>{invoice.vendorName}</h1>
          <p>
            {invoice.invoiceNumber || "Number not extracted"} · {invoice.propertyName} ·{" "}
            {invoice.workOrderNumber || "Work order not extracted"}
          </p>
        </div>
        <div className="detail-header__status">
          <StatusBadge status={invoice.status} />
          <DueDateFlag dueDate={invoice.dueDate} status={invoice.status} />
        </div>
      </header>

      <div className="detail-grid">
        <section className="detail-card" aria-labelledby="extracted-fields-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Textract preview</p>
              <h2 id="extracted-fields-title">{canReview ? "Review extracted fields" : "Extracted fields"}</h2>
            </div>
            <span>{Math.round(invoice.extractionConfidence * 100)}% confidence</span>
          </div>

          {canReview ? (
            <InvoiceReviewForm key={invoice.id} invoice={invoice} />
          ) : (
            <>
              <dl className="detail-list">
                <div>
                  <dt>Invoice number</dt>
                  <dd>{invoice.invoiceNumber}</dd>
                </div>
                <div>
                  <dt>Invoice date</dt>
                  <dd>{invoice.invoiceDate ? formatDateOnly(invoice.invoiceDate) : "Not extracted"}</dd>
                </div>
                <div>
                  <dt>Due date</dt>
                  <dd>{invoice.dueDate ? formatDateOnly(invoice.dueDate) : "Not extracted"}</dd>
                </div>
                <div>
                  <dt>Work order</dt>
                  <dd>{invoice.workOrderNumber}</dd>
                </div>
              </dl>

              <div className="invoice-lines">
                {invoice.lineItems.map((line) => (
                  <div key={line.id}>
                    <span>
                      {line.description}
                      <small>
                        {line.quantity} × {formatCents(line.unitPriceCents)}
                      </small>
                    </span>
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
            </>
          )}
        </section>

        <aside className="detail-stack">
          <section className="detail-card" aria-labelledby="decision-title">
            <p className="eyebrow">Human workflow</p>
            <h2 id="decision-title">
              {invoice.status === "PENDING_APPROVAL" ? "Approval decision" : "Review context"}
            </h2>
            <p className="detail-copy">{invoice.reviewNote || "No review note has been recorded."}</p>

            {canDecide ? <DecisionPanel key={invoice.id} invoice={invoice} /> : null}
            {invoice.status === "PENDING_REVIEW" && !canReview ? (
              <div className="permission-note" role="note">
                AP clerk access is required to edit and submit these fields.
              </div>
            ) : null}
            {invoice.status === "PENDING_APPROVAL" && !canDecide ? (
              <div className="permission-note" role="note">
                Only the assigned property manager can approve or reject this invoice.
              </div>
            ) : null}
            {["APPROVED", "REJECTED"].includes(invoice.status) ? (
              <div className="decision-record">
                <strong>Recorded decision reason</strong>
                <p>{invoice.decisionReason}</p>
              </div>
            ) : null}
          </section>

          <section className="detail-card" aria-labelledby="source-document-title">
            <p className="eyebrow">Source document</p>
            <h2 id="source-document-title">Local fixture</h2>
            <p className="detail-copy source-file-name">{invoice.sourceFileName}</p>
            <p className="fixture-disclaimer">Synthetic data only · no S3 object or network upload exists in mock mode.</p>
          </section>

          <section className="detail-card" aria-labelledby="audit-title">
            <p className="eyebrow">Append-only record</p>
            <h2 id="audit-title">Audit history</h2>
            <ol className="audit-list">
              {invoice.audit.map((entry) => (
                <li key={entry.id}>
                  <strong>{entry.action}</strong>
                  <span>
                    {entry.actorName} · {new Date(entry.createdAt).toLocaleString()}
                  </span>
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
