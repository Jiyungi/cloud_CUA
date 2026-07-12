export type UserRole = "vendor" | "ap_clerk" | "property_manager" | "finance_admin";

export type InvoiceStatus =
  | "UPLOADED"
  | "EXTRACTING"
  | "PENDING_REVIEW"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED";

export interface AppUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  tenantId: string;
  vendorId?: string;
  propertyIds: string[];
}

export interface InvoiceLineItem {
  id: string;
  description: string;
  quantity: number;
  unitPriceCents: number;
  amountCents: number;
  confidence: number;
}

export interface AuditEntry {
  id: string;
  action: string;
  actorName: string;
  actorRole: UserRole | "system";
  createdAt: string;
  detail: string;
}

export interface Invoice {
  id: string;
  tenantId: string;
  vendorId: string;
  vendorName: string;
  propertyId: string;
  propertyName: string;
  assignedManagerId: string;
  invoiceNumber: string;
  invoiceDate: string;
  dueDate: string;
  workOrderNumber: string;
  sourceFileName: string;
  subtotalCents: number;
  taxCents: number;
  totalCents: number;
  extractionConfidence: number;
  status: InvoiceStatus;
  lineItems: InvoiceLineItem[];
  audit: AuditEntry[];
  reviewNote: string;
  decisionReason: string;
}

export interface InvoicePatch {
  invoiceNumber?: string;
  invoiceDate?: string;
  dueDate?: string;
  workOrderNumber?: string;
  subtotalCents?: number;
  taxCents?: number;
  totalCents?: number;
  lineItems?: InvoiceLineItem[];
  reviewNote?: string;
}

export interface UploadRequest {
  fileName: string;
  fileType: string;
  fileSize: number;
  vendorId: string;
  propertyId: string;
}

export interface UploadTicket {
  invoiceId: string;
  uploadUrl: string;
  objectKey: string;
}

export interface DecisionRequest {
  decision: "APPROVED" | "REJECTED";
  reason: string;
}
