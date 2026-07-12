import { Link } from "react-router-dom";
import type { Invoice } from "../models";
import { formatCents } from "../utils/money";
import { DueDateFlag } from "./DueDateFlag";
import { StatusBadge } from "./StatusBadge";

interface InvoiceTableProps {
  invoices: Invoice[];
  emptyMessage: string;
}

export function InvoiceTable({ invoices, emptyMessage }: InvoiceTableProps): React.JSX.Element {
  if (invoices.length === 0) {
    return <div className="empty-state">{emptyMessage}</div>;
  }

  return (
    <div className="table-frame">
      <table>
        <thead>
          <tr>
            <th scope="col">Vendor / invoice</th>
            <th scope="col">Property</th>
            <th scope="col">Due</th>
            <th scope="col">Amount</th>
            <th scope="col">Status</th>
            <th scope="col">
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((invoice) => (
            <tr key={invoice.id}>
              <td>
                <strong>{invoice.vendorName}</strong>
                <span>{invoice.invoiceNumber || "Number not extracted"}</span>
              </td>
              <td>{invoice.propertyName}</td>
              <td>
                <DueDateFlag dueDate={invoice.dueDate} status={invoice.status} />
              </td>
              <td className="table-amount">{formatCents(invoice.totalCents)}</td>
              <td>
                <StatusBadge status={invoice.status} />
              </td>
              <td>
                <Link className="table-link" to={`/invoices/${invoice.id}`} aria-label={`Open ${invoice.invoiceNumber}`}>
                  Open <span aria-hidden="true">→</span>
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
