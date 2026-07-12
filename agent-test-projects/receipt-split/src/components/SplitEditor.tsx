import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { Participant, Receipt, ReceiptItem } from "../models";
import { useAppState } from "../state/AppStateContext";
import { formatCents } from "../utils/money";
import { calculateParticipantShares, hasCompleteAssignments } from "../utils/split";

interface SplitEditorProps {
  receipt: Receipt;
}

export function SplitEditor({ receipt }: SplitEditorProps): React.JSX.Element {
  const { api, refreshReceipts } = useAppState();
  const [participants, setParticipants] = useState<Participant[]>(structuredClone(receipt.participants));
  const [items, setItems] = useState<ReceiptItem[]>(structuredClone(receipt.items));
  const [friendName, setFriendName] = useState("");
  const [friendEmail, setFriendEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const calculatedParticipants = useMemo(
    () => calculateParticipantShares(receipt.totalCents, items, participants),
    [items, participants, receipt.totalCents],
  );
  const allocatedCents = calculatedParticipants.reduce(
    (sum, participant) => sum + participant.amountOwedCents,
    0,
  );
  const assignmentsComplete = hasCompleteAssignments(items) && participants.length > 0;

  function toggleAssignment(itemId: string, participantId: string): void {
    setItems((current) =>
      current.map((item) => {
        if (item.id !== itemId) {
          return item;
        }
        const assigned = item.participantIds.includes(participantId);
        return {
          ...item,
          participantIds: assigned
            ? item.participantIds.filter((id) => id !== participantId)
            : [...item.participantIds, participantId],
        };
      }),
    );
    setNotice(null);
  }

  function splitEveryItemEqually(): void {
    const participantIds = participants.map((participant) => participant.id);
    setItems((current) => current.map((item) => ({ ...item, participantIds })));
    setNotice("Every item is now shared by all friends.");
  }

  function addFriend(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const name = friendName.trim();
    const email = friendEmail.trim();
    if (!name || !email) {
      setError("Friend name and email are required.");
      return;
    }

    const id = `friend-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${participants.length + 1}`;
    setParticipants((current) => [
      ...current,
      { id, name, email, amountOwedCents: 0, paid: false },
    ]);
    setFriendName("");
    setFriendEmail("");
    setError(null);
    setNotice(`${name} was added. Assign shared items as needed before saving.`);
  }

  async function saveSplit(): Promise<void> {
    if (!assignmentsComplete || allocatedCents !== receipt.totalCents) {
      setError("Assign every item and make sure the full receipt total is allocated.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await api.saveSplit(receipt.id, { participants: calculatedParticipants, items });
      await refreshReceipts();
      setParticipants(calculatedParticipants);
      setNotice("Split saved locally. No network request was made.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save this split.");
    } finally {
      setSaving(false);
    }
  }

  async function sendReminder(): Promise<void> {
    try {
      await api.sendReminder(receipt.id);
      setNotice("Demo reminder scheduled locally for unpaid friends.");
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to schedule a reminder.");
    }
  }

  async function markPaid(participantId: string): Promise<void> {
    try {
      const updated = await api.markPaid(receipt.id, participantId);
      setParticipants(structuredClone(updated.participants));
      await refreshReceipts();
      setNotice("Payment status updated locally.");
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update payment status.");
    }
  }

  return (
    <div className="page-stack">
      <section className="split-total">
        <span>Receipt total</span>
        <strong>{formatCents(receipt.totalCents)}</strong>
        <div className="allocation-meter" aria-label={`${formatCents(allocatedCents)} allocated`}>
          <span style={{ width: `${Math.min((allocatedCents / receipt.totalCents) * 100, 100)}%` }} />
        </div>
        <small>
          {formatCents(allocatedCents)} allocated · {assignmentsComplete ? "ready to save" : "assignment needed"}
        </small>
      </section>

      <section className="form-card" aria-labelledby="assignment-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Item allocation</p>
            <h2 id="assignment-title">Who shared each item?</h2>
          </div>
          <button className="text-button" type="button" onClick={splitEveryItemEqually}>
            Split all equally
          </button>
        </div>

        <div className="assignment-list">
          {items.map((item) => (
            <fieldset className="assignment-card" key={item.id}>
              <legend>
                <span>{item.name}</span>
                <strong>{formatCents(item.amountCents)}</strong>
              </legend>
              <div className="assignment-options">
                {participants.map((participant) => (
                  <label key={participant.id}>
                    <input
                      type="checkbox"
                      checked={item.participantIds.includes(participant.id)}
                      onChange={() => toggleAssignment(item.id, participant.id)}
                    />
                    <span>{participant.name}</span>
                  </label>
                ))}
              </div>
              {item.participantIds.length === 0 ? (
                <small className="field-warning">Assign at least one friend.</small>
              ) : null}
            </fieldset>
          ))}
        </div>
      </section>

      <section aria-labelledby="friends-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Friends</p>
            <h2 id="friends-title">Who owes what</h2>
          </div>
        </div>

        <div className="participant-list">
          {calculatedParticipants.map((participant) => (
            <article className="participant-card" key={participant.id}>
              <span className="participant-card__avatar" aria-hidden="true">
                {participant.name.slice(0, 1)}
              </span>
              <div className="participant-card__identity">
                <strong>{participant.name}</strong>
                <span>{participant.paid ? "Paid" : "Waiting"}</span>
              </div>
              <div className="participant-card__amount">
                <strong>{formatCents(participant.amountOwedCents)}</strong>
                {!participant.paid ? (
                  <button type="button" onClick={() => void markPaid(participant.id)}>
                    Mark paid
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>

        <form className="friend-form" onSubmit={addFriend}>
          <label>
            Friend name
            <input value={friendName} onChange={(event) => setFriendName(event.target.value)} required />
          </label>
          <label>
            Email
            <input
              value={friendEmail}
              onChange={(event) => setFriendEmail(event.target.value)}
              required
              type="email"
            />
          </label>
          <button className="button button--secondary" type="submit">
            Add friend
          </button>
        </form>
      </section>

      {notice ? <div className="success-state" role="status">{notice}</div> : null}
      {error ? <div className="error-state" role="alert">{error}</div> : null}

      <div className="action-stack">
        <button
          className="button button--primary button--full"
          type="button"
          disabled={!assignmentsComplete || saving}
          onClick={() => void saveSplit()}
        >
          {saving ? "Saving…" : "Save exact split"}
        </button>
        <button className="button button--secondary button--full" type="button" onClick={() => void sendReminder()}>
          Remind unpaid friends
        </button>
        <Link className="button button--ghost button--full" to="/receipts">
          Back to receipts
        </Link>
      </div>
    </div>
  );
}
