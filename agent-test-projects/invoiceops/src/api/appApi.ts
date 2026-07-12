import type {
  AppUser,
  DecisionRequest,
  Invoice,
  InvoicePatch,
  UploadRequest,
  UploadTicket,
} from "../models";

export interface AppApi {
  health(): Promise<{ ok: true; environment: string }>;
  getMe(): Promise<AppUser>;
  listInvoices(): Promise<Invoice[]>;
  getInvoice(invoiceId: string): Promise<Invoice>;
  createUpload(request: UploadRequest): Promise<UploadTicket>;
  updateExtractedFields(invoiceId: string, patch: InvoicePatch): Promise<Invoice>;
  decideInvoice(invoiceId: string, request: DecisionRequest): Promise<Invoice>;
}

export class ApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}
