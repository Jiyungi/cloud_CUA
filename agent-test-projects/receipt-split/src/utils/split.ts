import type { Participant, ReceiptItem } from "../models";

function distributeCents(totalCents: number, participantIds: string[]): Map<string, number> {
  const distribution = new Map<string, number>();
  if (participantIds.length === 0) {
    return distribution;
  }

  const baseShare = Math.floor(totalCents / participantIds.length);
  const remainder = totalCents % participantIds.length;

  participantIds.forEach((participantId, index) => {
    distribution.set(participantId, baseShare + (index < remainder ? 1 : 0));
  });
  return distribution;
}

export function hasCompleteAssignments(items: ReceiptItem[]): boolean {
  return items.length > 0 && items.every((item) => item.participantIds.length > 0);
}

export function calculateParticipantShares(
  totalCents: number,
  items: ReceiptItem[],
  participants: Participant[],
): Participant[] {
  const amounts = new Map(participants.map((participant) => [participant.id, 0]));

  for (const item of items) {
    const itemShares = distributeCents(item.amountCents, item.participantIds);
    for (const [participantId, share] of itemShares) {
      amounts.set(participantId, (amounts.get(participantId) ?? 0) + share);
    }
  }

  const itemTotal = items.reduce((sum, item) => sum + item.amountCents, 0);
  const sharedCharges = Math.max(totalCents - itemTotal, 0);
  const chargeShares = distributeCents(
    sharedCharges,
    participants.map((participant) => participant.id),
  );
  for (const [participantId, share] of chargeShares) {
    amounts.set(participantId, (amounts.get(participantId) ?? 0) + share);
  }

  return participants.map((participant) => ({
    ...participant,
    amountOwedCents: amounts.get(participant.id) ?? 0,
  }));
}
