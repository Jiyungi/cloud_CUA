import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { Receipt, ReceiptItem } from "../models";
import { useAppState } from "../state/AppStateContext";
import { centsToInput, formatCents, inputToCents } from "../utils/money";

interface ReceiptReviewFormProps {
  receipt: Receipt;
}

export function ReceiptReviewForm({ receipt }: ReceiptReviewFormProps): React.JSX.Element {
  const navigate = useNavigate();
  const { api, refreshReceipts } = useAppState();
  const [merchant, setMerchant] = useState(receipt.merchant);
  const [purchasedAt, setPurchasedAt] = useState(receipt.purchasedAt);
  const [tax, setTax] = useState(centsToInput(receipt.taxCents));
  const [tip, setTip] = useState(centsToInput(receipt.tipCents));
  const [items, setItems] = useState<ReceiptItem[]>(structuredClone(receipt.items));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const subtotalCents = items.reduce((sum, item) => sum + item.amountCents, 0);
  const totalCents = subtotalCents + inputToCents(tax) + inputToCents(tip);

  function updateItem(itemId: string, patch: Partial<ReceiptItem>): void {
    setItems((current) =>
      current.map((item) => (item.id === itemId ? { ...item, ...patch } : item)),
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!merchant.trim() || !purchasedAt || items.some((item) => !item.name.trim())) {
      setError("Merchant, date, and every item name are required.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await api.updateReceipt(receipt.id, {
        merchant: merchant.trim(),
        purchasedAt,
        taxCents: inputToCents(tax),
        tipCents: inputToCents(tip),
        items,
      });
      await api.confirmReceipt(receipt.id);
      await refreshReceipts();
      navigate(`/receipts/${receipt.id}/split`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to confirm this receipt.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="form-card" onSubmit={(event) => void handleSubmit(event)}>
      <div className="field-grid">
        <label>
          Merchant
          <input value={merchant} onChange={(event) => setMerchant(event.target.value)} required />
        </label>
        <label>
          Purchase date
          <input
            value={purchasedAt}
            onChange={(event) => setPurchasedAt(event.target.value)}
            required
            type="date"
          />
        </label>
      </div>

      <div className="line-items" aria-labelledby="line-items-title">
        <div className="section-heading section-heading--compact">
          <h2 id="line-items-title">Line items</h2>
          <span>{Math.round(receipt.extractionConfidence * 100)}% overall confidence</span>
        </div>
        {items.map((item) => (
          <fieldset className="editable-line-item" key={item.id}>
            <legend>
              Extracted item · {Math.round(item.confidence * 100)}% confidence
            </legend>
            <label>
              Item
              <input
                value={item.name}
                onChange={(event) => updateItem(item.id, { name: event.target.value })}
                required
              />
            </label>
            <label>
              Quantity
              <input
                min="1"
                step="1"
                type="number"
                value={item.quantity}
                onChange={(event) =>
                  updateItem(item.id, { quantity: Math.max(1, Number(event.target.value) || 1) })
                }
              />
            </label>
            <label>
              Amount
              <span className="currency-input">
                <span aria-hidden="true">$</span>
                <input
                  min="0"
                  step="0.01"
                  inputMode="decimal"
                  type="number"
                  value={centsToInput(item.amountCents)}
                  onChange={(event) =>
                    updateItem(item.id, { amountCents: inputToCents(event.target.value) })
                  }
                />
              </span>
            </label>
          </fieldset>
        ))}
      </div>

      <div className="field-grid">
        <label>
          Tax
          <span className="currency-input">
            <span aria-hidden="true">$</span>
            <input
              min="0"
              step="0.01"
              inputMode="decimal"
              type="number"
              value={tax}
              onChange={(event) => setTax(event.target.value)}
            />
          </span>
        </label>
        <label>
          Tip
          <span className="currency-input">
            <span aria-hidden="true">$</span>
            <input
              min="0"
              step="0.01"
              inputMode="decimal"
              type="number"
              value={tip}
              onChange={(event) => setTip(event.target.value)}
            />
          </span>
        </label>
      </div>

      <dl className="totals-list">
        <div>
          <dt>Subtotal</dt>
          <dd>{formatCents(subtotalCents)}</dd>
        </div>
        <div>
          <dt>Tax and tip</dt>
          <dd>{formatCents(inputToCents(tax) + inputToCents(tip))}</dd>
        </div>
        <div className="totals-list__total">
          <dt>Reviewed total</dt>
          <dd>{formatCents(totalCents)}</dd>
        </div>
      </dl>

      {error ? <div className="error-state" role="alert">{error}</div> : null}

      <button className="button button--primary button--full" type="submit" disabled={saving}>
        {saving ? "Confirming…" : "Confirm and continue"}
      </button>
    </form>
  );
}
