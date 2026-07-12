export type ReceiptStatus = "NEEDS_REVIEW" | "READY_TO_SPLIT" | "PARTIALLY_PAID" | "SETTLED";

export interface ReceiptItem {
  id: string;
  name: string;
  quantity: number;
  amountCents: number;
  confidence: number;
  participantIds: string[];
}

export interface Participant {
  id: string;
  name: string;
  email: string;
  amountOwedCents: number;
  paid: boolean;
}

export interface Receipt {
  id: string;
  sourceFileName: string;
  merchant: string;
  purchasedAt: string;
  subtotalCents: number;
  taxCents: number;
  tipCents: number;
  totalCents: number;
  status: ReceiptStatus;
  extractionConfidence: number;
  items: ReceiptItem[];
  participants: Participant[];
  createdAt: string;
}

export interface UploadRequest {
  fileName: string;
  fileType: string;
  fileSize: number;
}

export interface UploadTicket {
  receiptId: string;
  uploadUrl: string;
  objectKey: string;
}

export interface ReceiptPatch {
  merchant?: string;
  purchasedAt?: string;
  taxCents?: number;
  tipCents?: number;
  items?: ReceiptItem[];
}

export interface SplitInput {
  participants: Participant[];
  items: ReceiptItem[];
}
