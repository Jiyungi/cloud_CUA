import { SEEDED_RECEIPTS } from "../data/seed";
import type { Participant, Receipt, ReceiptPatch, SplitInput, UploadRequest, UploadTicket } from "../models";
import type { AppApi } from "./appApi";
import { ApiError } from "./appApi";

const STORAGE_KEY = "receipt-split:mock-receipts:v1";

function cloneReceipts(receipts: Receipt[]): Receipt[] {
  return structuredClone(receipts);
}

function readReceipts(): Receipt[] {
  const saved = window.localStorage.getItem(STORAGE_KEY);
  if (!saved) {
    return cloneReceipts(SEEDED_RECEIPTS);
  }

  try {
    return JSON.parse(saved) as Receipt[];
  } catch {
    return cloneReceipts(SEEDED_RECEIPTS);
  }
}

function writeReceipts(receipts: Receipt[]): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(receipts));
}

function findReceipt(receipts: Receipt[], receiptId: string): Receipt {
  const receipt = receipts.find((candidate) => candidate.id === receiptId);
  if (!receipt) {
    throw new ApiError("NOT_FOUND", `Receipt ${receiptId} was not found.`);
  }
  return receipt;
}

function replaceReceipt(receipts: Receipt[], updated: Receipt): Receipt {
  const next = receipts.map((receipt) => (receipt.id === updated.id ? updated : receipt));
  writeReceipts(next);
  return structuredClone(updated);
}

function settlementStatus(participants: Participant[]): Receipt["status"] {
  if (participants.length > 0 && participants.every((participant) => participant.paid)) {
    return "SETTLED";
  }
  if (participants.some((participant) => participant.paid)) {
    return "PARTIALLY_PAID";
  }
  return "READY_TO_SPLIT";
}

export const mockApi: AppApi = {
  async health() {
    return { ok: true, environment: "mock" };
  },

  async listReceipts() {
    return cloneReceipts(readReceipts());
  },

  async getReceipt(receiptId) {
    return structuredClone(findReceipt(readReceipts(), receiptId));
  },

  async createUpload(request: UploadRequest): Promise<UploadTicket> {
    const receiptId = `receipt-${request.fileName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    return {
      receiptId,
      uploadUrl: `blob:mock-upload/${receiptId}`,
      objectKey: `mock/${receiptId}/${request.fileName}`,
    };
  },

  async updateReceipt(receiptId, patch: ReceiptPatch) {
    const receipts = readReceipts();
    const current = findReceipt(receipts, receiptId);
    return replaceReceipt(receipts, { ...current, ...structuredClone(patch) });
  },

  async confirmReceipt(receiptId) {
    const receipts = readReceipts();
    const current = findReceipt(receipts, receiptId);
    return replaceReceipt(receipts, { ...current, status: "READY_TO_SPLIT" });
  },

  async saveSplit(receiptId, input: SplitInput) {
    const receipts = readReceipts();
    const current = findReceipt(receipts, receiptId);
    const updated: Receipt = {
      ...current,
      participants: structuredClone(input.participants),
      items: structuredClone(input.items),
      status: settlementStatus(input.participants),
    };
    return replaceReceipt(receipts, updated);
  },

  async sendReminder(receiptId) {
    findReceipt(readReceipts(), receiptId);
    return { scheduled: true };
  },

  async markPaid(receiptId, participantId) {
    const receipts = readReceipts();
    const current = findReceipt(receipts, receiptId);
    const participants = current.participants.map((participant) =>
      participant.id === participantId ? { ...participant, paid: true } : participant,
    );
    return replaceReceipt(receipts, {
      ...current,
      participants,
      status: settlementStatus(participants),
    });
  },
};
