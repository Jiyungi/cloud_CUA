import type { Receipt } from "../models";

export const SEEDED_RECEIPTS: Receipt[] = [
  {
    id: "receipt-harbor-table",
    sourceFileName: "synthetic-harbor-table-receipt.png",
    merchant: "Harbor Table",
    purchasedAt: "2026-07-09",
    subtotalCents: 7200,
    taxCents: 648,
    tipCents: 1552,
    totalCents: 9400,
    status: "READY_TO_SPLIT",
    extractionConfidence: 0.94,
    createdAt: "2026-07-09T20:14:00.000Z",
    items: [
      {
        id: "item-noodles",
        name: "Garlic noodles",
        quantity: 2,
        amountCents: 3200,
        confidence: 0.98,
        participantIds: ["friend-maya", "friend-jordan"],
      },
      {
        id: "item-salad",
        name: "Market salad",
        quantity: 1,
        amountCents: 1800,
        confidence: 0.95,
        participantIds: ["friend-alex"],
      },
      {
        id: "item-dessert",
        name: "Citrus cake",
        quantity: 1,
        amountCents: 2200,
        confidence: 0.88,
        participantIds: ["friend-maya", "friend-jordan", "friend-alex"],
      },
    ],
    participants: [
      {
        id: "friend-maya",
        name: "Maya",
        email: "maya@example.test",
        amountOwedCents: 3600,
        paid: true,
      },
      {
        id: "friend-jordan",
        name: "Jordan",
        email: "jordan@example.test",
        amountOwedCents: 3200,
        paid: false,
      },
      {
        id: "friend-alex",
        name: "Alex",
        email: "alex@example.test",
        amountOwedCents: 2600,
        paid: false,
      },
    ],
  },
];

export function createExtractedReceipt(receiptId: string, sourceFileName: string): Receipt {
  return {
    id: receiptId,
    sourceFileName,
    merchant: "Sunset Market",
    purchasedAt: "2026-07-10",
    subtotalCents: 5025,
    taxCents: 422,
    tipCents: 0,
    totalCents: 5447,
    status: "NEEDS_REVIEW",
    extractionConfidence: 0.86,
    createdAt: "2026-07-10T18:42:00.000Z",
    items: [
      {
        id: `${receiptId}-berries`,
        name: "Organic berries",
        quantity: 2,
        amountCents: 1298,
        confidence: 0.96,
        participantIds: ["friend-maya"],
      },
      {
        id: `${receiptId}-bread`,
        name: "Sourdough bread",
        quantity: 1,
        amountCents: 799,
        confidence: 0.93,
        participantIds: ["friend-jordan"],
      },
      {
        id: `${receiptId}-picnic`,
        name: "Picnic supplies",
        quantity: 1,
        amountCents: 2928,
        confidence: 0.68,
        participantIds: ["friend-maya", "friend-jordan", "friend-alex"],
      },
    ],
    participants: [
      {
        id: "friend-maya",
        name: "Maya",
        email: "maya@example.test",
        amountOwedCents: 0,
        paid: false,
      },
      {
        id: "friend-jordan",
        name: "Jordan",
        email: "jordan@example.test",
        amountOwedCents: 0,
        paid: false,
      },
      {
        id: "friend-alex",
        name: "Alex",
        email: "alex@example.test",
        amountOwedCents: 0,
        paid: false,
      },
    ],
  };
}
