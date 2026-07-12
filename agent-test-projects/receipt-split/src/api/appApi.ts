import type { Receipt, ReceiptPatch, SplitInput, UploadRequest, UploadTicket } from "../models";

export interface AppApi {
  health(): Promise<{ ok: true; environment: string }>;
  listReceipts(): Promise<Receipt[]>;
  getReceipt(receiptId: string): Promise<Receipt>;
  createUpload(request: UploadRequest): Promise<UploadTicket>;
  updateReceipt(receiptId: string, patch: ReceiptPatch): Promise<Receipt>;
  confirmReceipt(receiptId: string): Promise<Receipt>;
  saveSplit(receiptId: string, input: SplitInput): Promise<Receipt>;
  sendReminder(receiptId: string): Promise<{ scheduled: true }>;
  markPaid(receiptId: string, participantId: string): Promise<Receipt>;
}

export class ApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}
