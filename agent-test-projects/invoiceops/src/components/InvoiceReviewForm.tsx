import { useMemo, useRef, useState, type FormEvent } from "react";
import type { Invoice, InvoiceLineItem } from "../models";
import { useAppState } from "../state/AppStateContext";
import { centsToInput, formatCents, parseDollarInput } from "../utils/money";

interface InvoiceReviewFormProps {
  invoice: Invoice;
}

interface EditableLineItem {
  id: string;
  description: string;
  quantity: string;
  unitPrice: string;
  confidence: number;
}

function editableLine(line: InvoiceLineItem): EditableLineItem {
  return {
    id: line.id,
    description: line.description,
    quantity: String(line.quantity),
    unitPrice: centsToInput(line.unitPriceCents),
    confidence: line.confidence,
  };
}

export function InvoiceReviewForm({ invoice }: InvoiceReviewFormProps): React.JSX.Element {
  const { api, refresh } = useAppState();
  const [invoiceNumber, setInvoiceNumber] = useState(invoice.invoiceNumber);
  const [invoiceDate, setInvoiceDate] = useState(invoice.invoiceDate);
  const [dueDate, setDueDate] = useState(invoice.dueDate);
  const [workOrderNumber, setWorkOrderNumber] = useState(invoice.workOrderNumber);
  const [lines, setLines] = useState<EditableLineItem[]>(() =>
    invoice.lineItems.length > 0
      ? invoice.lineItems.map(editableLine)
      : [
          {
            id: `line-review-${invoice.id}-1`,
            description: "",
            quantity: "1",
            unitPrice: "0.00",
            confidence: 1,
          },
        ],
  );
  const [tax, setTax] = useState(centsToInput(invoice.taxCents));
  const [reviewNote, setReviewNote] = useState(invoice.reviewNote);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lineCounter = useRef(Math.max(invoice.lineItems.length, 1));

  const calculated = useMemo(() => {
    const normalized = lines.map((line) => ({
      quantity: Number(line.quantity),
      unitPriceCents: parseDollarInput(line.unitPrice),
    }));
    if (
      normalized.some(
        (line) => !Number.isSafeInteger(line.quantity) || line.quantity <= 0 || line.unitPriceCents === null,
      )
    ) {
      return null;
    }
    const subtotalCents = normalized.reduce(
      (sum, line) => sum + line.quantity * (line.unitPriceCents ?? 0),
      0,
    );
    const taxCents = parseDollarInput(tax);
    const totalCents = subtotalCents + (taxCents ?? 0);
    return taxCents === null || !Number.isSafeInteger(subtotalCents) || !Number.isSafeInteger(totalCents)
      ? null
      : { subtotalCents, taxCents, totalCents };
  }, [lines, tax]);

  function updateLine(id: string, patch: Partial<EditableLineItem>): void {
    setLines((current) => current.map((line) => (line.id === id ? { ...line, ...patch } : line)));
  }

  function addLine(): void {
    lineCounter.current += 1;
    setLines((current) => [
      ...current,
      {
        id: `line-review-${invoice.id}-${lineCounter.current}`,
        description: "",
        quantity: "1",
        unitPrice: "0.00",
        confidence: 1,
      },
    ]);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!calculated) {
      setError("Enter whole-number quantities and dollar amounts with no more than two decimal places.");
      return;
    }
    const lineItems: InvoiceLineItem[] = [];
    for (const [index, line] of lines.entries()) {
      const unitPriceCents = parseDollarInput(line.unitPrice);
      const quantity = Number(line.quantity);
      if (!line.description.trim() || unitPriceCents === null || !Number.isSafeInteger(quantity) || quantity <= 0) {
        setError(`Complete line item ${index + 1} before submitting.`);
        return;
      }
      lineItems.push({
        id: line.id,
        description: line.description,
        quantity,
        unitPriceCents,
        amountCents: quantity * unitPriceCents,
        confidence: line.confidence,
      });
    }

    try {
      setBusy(true);
      setError(null);
      await api.updateExtractedFields(invoice.id, {
        invoiceNumber,
        invoiceDate,
        dueDate,
        workOrderNumber,
        lineItems,
        subtotalCents: calculated.subtotalCents,
        taxCents: calculated.taxCents,
        totalCents: calculated.totalCents,
        reviewNote,
      });
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The extracted fields could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="review-form" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <div className="field-grid">
        <label>
          Invoice number
          <input value={invoiceNumber} onChange={(event) => setInvoiceNumber(event.target.value)} required />
        </label>
        <label>
          Work order
          <input value={workOrderNumber} onChange={(event) => setWorkOrderNumber(event.target.value)} required />
        </label>
        <label>
          Invoice date
          <input type="date" value={invoiceDate} onChange={(event) => setInvoiceDate(event.target.value)} required />
        </label>
        <label>
          Due date
          <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} required />
        </label>
      </div>

      <fieldset className="line-editor">
        <legend className="sr-only">Extracted line items</legend>
        <div className="line-editor__heading">
          <strong>Extracted line items</strong>
          <button className="text-button" type="button" onClick={addLine}>
            + Add line
          </button>
        </div>
        {lines.map((line, index) => (
          <div className="line-editor__row" key={line.id}>
            <label>
              <span>Description {index + 1}</span>
              <input
                value={line.description}
                onChange={(event) => updateLine(line.id, { description: event.target.value })}
                required
              />
            </label>
            <label>
              <span>Quantity</span>
              <input
                type="number"
                min="1"
                step="1"
                inputMode="numeric"
                value={line.quantity}
                onChange={(event) => updateLine(line.id, { quantity: event.target.value })}
                required
              />
            </label>
            <label>
              <span>Unit price</span>
              <input
                inputMode="decimal"
                value={line.unitPrice}
                onChange={(event) => updateLine(line.id, { unitPrice: event.target.value })}
                aria-label={`Unit price for line item ${index + 1}`}
                required
              />
            </label>
            <div className="line-editor__amount">
              <span>Amount</span>
              <strong>
                {parseDollarInput(line.unitPrice) === null || !Number.isSafeInteger(Number(line.quantity))
                  ? "—"
                  : formatCents(Number(line.quantity) * (parseDollarInput(line.unitPrice) ?? 0))}
              </strong>
            </div>
            {lines.length > 1 ? (
              <button
                className="icon-button"
                type="button"
                onClick={() => setLines((current) => current.filter((candidate) => candidate.id !== line.id))}
                aria-label={`Remove line item ${index + 1}`}
              >
                ×
              </button>
            ) : null}
          </div>
        ))}
      </fieldset>

      <div className="review-summary">
        <label>
          Tax (USD)
          <input inputMode="decimal" value={tax} onChange={(event) => setTax(event.target.value)} required />
        </label>
        <dl>
          <div>
            <dt>Subtotal</dt>
            <dd>{calculated ? formatCents(calculated.subtotalCents) : "—"}</dd>
          </div>
          <div>
            <dt>Total</dt>
            <dd>{calculated ? formatCents(calculated.totalCents) : "—"}</dd>
          </div>
        </dl>
      </div>

      <label className="stacked-field">
        Correction or verification note
        <textarea
          rows={4}
          value={reviewNote}
          onChange={(event) => setReviewNote(event.target.value)}
          placeholder="Describe what you checked or corrected."
          required
        />
      </label>

      {error ? (
        <div className="inline-error" role="alert">
          {error}
        </div>
      ) : null}
      <button className="button button--primary button--full" type="submit" disabled={busy}>
        {busy ? "Submitting…" : "Submit for property approval"}
      </button>
    </form>
  );
}
