import { describe, expect, it } from "vitest";
import type { Participant, ReceiptItem } from "../models";
import { calculateParticipantShares, hasCompleteAssignments } from "./split";

const participants: Participant[] = [
  { id: "a", name: "A", email: "a@example.test", amountOwedCents: 0, paid: false },
  { id: "b", name: "B", email: "b@example.test", amountOwedCents: 0, paid: false },
  { id: "c", name: "C", email: "c@example.test", amountOwedCents: 0, paid: false },
];

describe("exact receipt allocation", () => {
  it("distributes item remainders and shared charges without losing a cent", () => {
    const items: ReceiptItem[] = [
      {
        id: "item",
        name: "Shared item",
        quantity: 1,
        amountCents: 901,
        confidence: 1,
        participantIds: ["a", "b", "c"],
      },
    ];

    const result = calculateParticipantShares(1001, items, participants);

    expect(result.map((participant) => participant.amountOwedCents)).toEqual([335, 333, 333]);
    expect(result.reduce((sum, participant) => sum + participant.amountOwedCents, 0)).toBe(1001);
  });

  it("reports incomplete allocation when an item has no participant", () => {
    const items: ReceiptItem[] = [
      {
        id: "unassigned",
        name: "Unassigned item",
        quantity: 1,
        amountCents: 500,
        confidence: 1,
        participantIds: [],
      },
    ];

    expect(hasCompleteAssignments(items)).toBe(false);
  });
});
