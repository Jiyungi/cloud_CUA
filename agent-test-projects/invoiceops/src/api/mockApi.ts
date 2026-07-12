import {
  FIXTURE_PROPERTIES,
  FIXTURE_VENDORS,
  SEEDED_INVOICES,
  SEEDED_USERS,
  TENANT_ID,
} from "../data/seed";
import type {
  AppUser,
  AuditEntry,
  DecisionRequest,
  Invoice,
  InvoiceLineItem,
  InvoicePatch,
  UploadRequest,
  UploadTicket,
} from "../models";
import type { AppApi } from "./appApi";
import { ApiError } from "./appApi";

const INVOICES_KEY = "invoiceops:mock-invoices:v1";
const USER_KEY = "invoiceops:mock-user:v1";
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const ALLOWED_UPLOAD_TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);
const ALLOWED_UPLOAD_EXTENSIONS = new Set(["pdf", "jpg", "jpeg", "png"]);

function cloneInvoices(invoices: Invoice[]): Invoice[] {
  return structuredClone(invoices);
}

function readInvoices(): Invoice[] {
  const saved = window.localStorage.getItem(INVOICES_KEY);
  if (!saved) {
    return cloneInvoices(SEEDED_INVOICES);
  }
  try {
    return JSON.parse(saved) as Invoice[];
  } catch {
    return cloneInvoices(SEEDED_INVOICES);
  }
}

function writeInvoices(invoices: Invoice[]): void {
  window.localStorage.setItem(INVOICES_KEY, JSON.stringify(invoices));
}

function activeUser(): AppUser {
  const userId = window.localStorage.getItem(USER_KEY) ?? SEEDED_USERS[1]?.id;
  const user = SEEDED_USERS.find((candidate) => candidate.id === userId) ?? SEEDED_USERS[1];
  if (!user) {
    throw new ApiError("NO_FIXTURE_USER", "No mock user is configured.");
  }
  return structuredClone(user);
}

function visibleToUser(invoice: Invoice, user: AppUser): boolean {
  if (invoice.tenantId !== user.tenantId) {
    return false;
  }
  if (user.role === "vendor") {
    return invoice.vendorId === user.vendorId;
  }
  if (user.role === "property_manager") {
    return user.propertyIds.includes(invoice.propertyId);
  }
  return true;
}

function findVisibleInvoice(invoiceId: string): Invoice {
  const user = activeUser();
  const invoice = readInvoices().find(
    (candidate) => candidate.id === invoiceId && visibleToUser(candidate, user),
  );
  if (!invoice) {
    throw new ApiError("NOT_FOUND", "Invoice was not found or is not visible to this role.");
  }
  return invoice;
}

function replaceInvoice(updated: Invoice): Invoice {
  const invoices = readInvoices();
  writeInvoices(invoices.map((invoice) => (invoice.id === updated.id ? updated : invoice)));
  return structuredClone(updated);
}

function extensionOf(fileName: string): string {
  return fileName.split(".").pop()?.toLowerCase() ?? "";
}

function assertUploadRequest(request: UploadRequest): void {
  if (!request.fileName.trim()) {
    throw new ApiError("INVALID_FILE", "Choose a synthetic invoice file before continuing.");
  }
  if (!Number.isInteger(request.fileSize) || request.fileSize <= 0) {
    throw new ApiError("INVALID_FILE", "The selected file is empty or unreadable.");
  }
  if (request.fileSize > MAX_UPLOAD_BYTES) {
    throw new ApiError("FILE_TOO_LARGE", "Invoice files must be 10 MiB or smaller.");
  }
  if (
    !ALLOWED_UPLOAD_TYPES.has(request.fileType.toLowerCase()) &&
    !ALLOWED_UPLOAD_EXTENSIONS.has(extensionOf(request.fileName))
  ) {
    throw new ApiError("UNSUPPORTED_FILE", "Use a PDF, JPG, JPEG, or PNG invoice.");
  }
}

function uploadTimestamp(sequence: number, seconds: number): string {
  const timestamp = new Date(Date.UTC(2026, 6, 11, 18, sequence, seconds));
  return timestamp.toISOString();
}

function workflowTimestamp(invoice: Invoice): string {
  const timestamp = new Date(Date.UTC(2026, 6, 11, 20, invoice.audit.length, 0));
  return timestamp.toISOString();
}

function auditEntry(
  invoice: Invoice,
  entry: Omit<AuditEntry, "id">,
): AuditEntry {
  return {
    ...entry,
    id: `${invoice.id}-audit-${invoice.audit.length + 1}`,
  };
}

function fixtureLineItems(vendorId: string): InvoiceLineItem[] {
  if (vendorId === "vendor-greenline-electric") {
    return [
      {
        id: "line-upload-panel",
        description: "Electrical panel diagnostic and repair",
        quantity: 1,
        unitPriceCents: 450000,
        amountCents: 450000,
        confidence: 0.88,
      },
    ];
  }

  return [
    {
      id: "line-upload-compressor",
      description: "Rooftop compressor replacement - RTU-4",
      quantity: 1,
      unitPriceCents: 920000,
      amountCents: 920000,
      confidence: 0.96,
    },
    {
      id: "line-upload-labor",
      description: "Emergency installation labor",
      quantity: 8,
      unitPriceCents: 32500,
      amountCents: 260000,
      confidence: 0.71,
    },
  ];
}

function createExtractedInvoice(
  request: UploadRequest,
  invoiceId: string,
  sequence: number,
  actor: AppUser,
): Invoice {
  const vendor = FIXTURE_VENDORS.find((candidate) => candidate.id === request.vendorId);
  const property = FIXTURE_PROPERTIES.find((candidate) => candidate.id === request.propertyId);
  if (!vendor || !property) {
    throw new ApiError("INVALID_FIXTURE_REFERENCE", "Choose a configured fixture vendor and property.");
  }

  const extractionNeedsReview = /(?:corrupt|unreadable)/i.test(request.fileName);
  const lineItems = extractionNeedsReview ? [] : fixtureLineItems(vendor.id);
  const subtotalCents = lineItems.reduce((sum, line) => sum + line.amountCents, 0);
  const taxCents = extractionNeedsReview ? 0 : vendor.id === "vendor-pacific-hvac" ? 97350 : 37125;
  const baseInvoice: Invoice = {
    id: invoiceId,
    tenantId: TENANT_ID,
    vendorId: vendor.id,
    vendorName: vendor.name,
    propertyId: property.id,
    propertyName: property.name,
    assignedManagerId: property.assignedManagerId,
    invoiceNumber: extractionNeedsReview ? "" : vendor.id === "vendor-pacific-hvac" ? "PH-1048" : "GE-7782",
    invoiceDate: extractionNeedsReview ? "" : "2026-07-08",
    dueDate: extractionNeedsReview ? "" : "2026-07-22",
    workOrderNumber: extractionNeedsReview ? "" : vendor.id === "vendor-pacific-hvac" ? "WO-4821" : "WO-4832",
    sourceFileName: request.fileName,
    subtotalCents,
    taxCents,
    totalCents: subtotalCents + taxCents,
    extractionConfidence: extractionNeedsReview ? 0 : 0.83,
    status: "PENDING_REVIEW",
    lineItems,
    audit: [],
    reviewNote: extractionNeedsReview
      ? "Mock extraction could not read this document. AP must enter every field manually."
      : "Confirm the low-confidence service detail before submitting for approval.",
    decisionReason: "",
  };

  baseInvoice.audit = [
    {
      id: `${invoiceId}-audit-uploaded`,
      action: "Invoice uploaded",
      actorName: actor.name,
      actorRole: actor.role,
      createdAt: uploadTimestamp(sequence, 0),
      detail: `${request.fileName} entered the local UPLOADED state.`,
    },
    {
      id: `${invoiceId}-audit-extracting`,
      action: "Extraction started",
      actorName: "InvoiceOps",
      actorRole: "system",
      createdAt: uploadTimestamp(sequence, 3),
      detail: "The mock workflow entered EXTRACTING without making a network request.",
    },
    {
      id: `${invoiceId}-audit-review`,
      action: extractionNeedsReview ? "Extraction needs manual review" : "Extraction completed",
      actorName: "InvoiceOps",
      actorRole: "system",
      createdAt: uploadTimestamp(sequence, 8),
      detail: extractionNeedsReview
        ? "No extracted fixture fields were stored; the invoice entered PENDING_REVIEW for manual entry."
        : "Deterministic fields were stored and the invoice entered PENDING_REVIEW.",
    },
  ];

  return baseInvoice;
}

function assertIsoDate(value: string, label: string): void {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    throw new ApiError("INVALID_DATE", `${label} must be a valid date.`);
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    throw new ApiError("INVALID_DATE", `${label} must be a valid date.`);
  }
}

function normalizeLineItems(lineItems: InvoiceLineItem[]): InvoiceLineItem[] {
  if (lineItems.length === 0) {
    throw new ApiError("INVALID_LINE_ITEMS", "At least one line item is required.");
  }

  return lineItems.map((line, index) => {
    const description = line.description.trim();
    if (!description) {
      throw new ApiError("INVALID_LINE_ITEMS", `Line item ${index + 1} needs a description.`);
    }
    if (!Number.isSafeInteger(line.quantity) || line.quantity <= 0) {
      throw new ApiError("INVALID_LINE_ITEMS", `Line item ${index + 1} needs a whole-number quantity.`);
    }
    if (!Number.isSafeInteger(line.unitPriceCents) || line.unitPriceCents < 0) {
      throw new ApiError("INVALID_LINE_ITEMS", `Line item ${index + 1} needs a valid unit price.`);
    }
    const amountCents = line.quantity * line.unitPriceCents;
    if (!Number.isSafeInteger(amountCents)) {
      throw new ApiError("INVALID_LINE_ITEMS", `Line item ${index + 1} exceeds the fixture amount limit.`);
    }
    return {
      ...structuredClone(line),
      description,
      amountCents,
      confidence: 1,
    };
  });
}

export function setMockUser(userId: string): void {
  if (!SEEDED_USERS.some((user) => user.id === userId)) {
    throw new ApiError("INVALID_USER", "Unknown fixture user.");
  }
  window.localStorage.setItem(USER_KEY, userId);
}

export const mockApi: AppApi = {
  async health() {
    return { ok: true, environment: "mock" };
  },

  async getMe() {
    return activeUser();
  },

  async listInvoices() {
    const user = activeUser();
    return cloneInvoices(readInvoices().filter((invoice) => visibleToUser(invoice, user)));
  },

  async getInvoice(invoiceId) {
    return structuredClone(findVisibleInvoice(invoiceId));
  },

  async createUpload(request: UploadRequest): Promise<UploadTicket> {
    assertUploadRequest(request);
    const user = activeUser();
    if (user.role !== "vendor") {
      throw new ApiError("FORBIDDEN", "Only vendors can upload invoices.");
    }
    if (user.role === "vendor" && user.vendorId !== request.vendorId) {
      throw new ApiError("FORBIDDEN", "Vendors can upload only for their own company.");
    }

    const invoices = readInvoices();
    const sequence = invoices.filter((invoice) => invoice.id.startsWith("invoice-upload-")).length + 1;
    const invoiceId = `invoice-upload-${sequence}`;
    const invoice = createExtractedInvoice(request, invoiceId, sequence, user);
    writeInvoices([
      { ...invoice, status: "UPLOADED", audit: invoice.audit.slice(0, 1) },
      ...invoices,
    ]);
    await Promise.resolve();
    writeInvoices([
      { ...invoice, status: "EXTRACTING", audit: invoice.audit.slice(0, 2) },
      ...invoices,
    ]);
    await Promise.resolve();
    writeInvoices([invoice, ...invoices]);

    return {
      invoiceId,
      uploadUrl: `blob:invoiceops-mock/${invoiceId}`,
      objectKey: `mock/${request.vendorId}/${request.propertyId}/${request.fileName.replaceAll("/", "-")}`,
    };
  },

  async updateExtractedFields(invoiceId, patch: InvoicePatch) {
    const user = activeUser();
    if (user.role !== "ap_clerk") {
      throw new ApiError("FORBIDDEN", "Only the AP clerk can correct extracted fields.");
    }
    const invoice = findVisibleInvoice(invoiceId);
    if (invoice.status !== "PENDING_REVIEW") {
      throw new ApiError("INVALID_STATE", "Only invoices pending AP review can be corrected.");
    }

    const invoiceNumber = (patch.invoiceNumber ?? invoice.invoiceNumber).trim();
    const invoiceDate = patch.invoiceDate ?? invoice.invoiceDate;
    const dueDate = patch.dueDate ?? invoice.dueDate;
    const workOrderNumber = (patch.workOrderNumber ?? invoice.workOrderNumber).trim();
    const reviewNote = (patch.reviewNote ?? invoice.reviewNote).trim();
    if (!invoiceNumber || !workOrderNumber) {
      throw new ApiError("INVALID_FIELDS", "Invoice number and work order are required.");
    }
    if (!reviewNote) {
      throw new ApiError("INVALID_REVIEW_NOTE", "Record a correction or verification note.");
    }
    assertIsoDate(invoiceDate, "Invoice date");
    assertIsoDate(dueDate, "Due date");
    if (dueDate < invoiceDate) {
      throw new ApiError("INVALID_DATE", "Due date cannot be before the invoice date.");
    }

    const lineItems = normalizeLineItems(patch.lineItems ?? invoice.lineItems);
    const subtotalCents = lineItems.reduce((sum, line) => sum + line.amountCents, 0);
    const taxCents = patch.taxCents ?? invoice.taxCents;
    if (!Number.isSafeInteger(subtotalCents)) {
      throw new ApiError("INVALID_TOTAL", "The line-item subtotal exceeds the fixture amount limit.");
    }
    if (!Number.isSafeInteger(taxCents) || taxCents < 0) {
      throw new ApiError("INVALID_TAX", "Tax must be a non-negative amount in cents.");
    }
    const totalCents = subtotalCents + taxCents;
    if (!Number.isSafeInteger(totalCents)) {
      throw new ApiError("INVALID_TOTAL", "The invoice total exceeds the fixture amount limit.");
    }
    if (patch.subtotalCents !== undefined && patch.subtotalCents !== subtotalCents) {
      throw new ApiError("TOTAL_MISMATCH", "Subtotal must equal the sum of the line items.");
    }
    if (patch.totalCents !== undefined && patch.totalCents !== totalCents) {
      throw new ApiError("TOTAL_MISMATCH", "Total must equal subtotal plus tax.");
    }

    const updated: Invoice = {
      ...invoice,
      invoiceNumber,
      invoiceDate,
      dueDate,
      workOrderNumber,
      reviewNote,
      lineItems,
      subtotalCents,
      taxCents,
      totalCents,
      extractionConfidence: 1,
      status: "PENDING_APPROVAL",
    };
    updated.audit = [
      ...invoice.audit,
      auditEntry(invoice, {
        action: "AP review completed",
        actorName: user.name,
        actorRole: user.role,
        createdAt: workflowTimestamp(invoice),
        detail: `${reviewNote} Invoice entered PENDING_APPROVAL.`,
      }),
    ];
    return replaceInvoice(updated);
  },

  async decideInvoice(invoiceId, request: DecisionRequest) {
    const user = activeUser();
    const invoice = findVisibleInvoice(invoiceId);
    if (user.role !== "property_manager" || invoice.assignedManagerId !== user.id) {
      throw new ApiError("FORBIDDEN", "Only the assigned property manager can decide this invoice.");
    }
    if (invoice.status !== "PENDING_APPROVAL") {
      throw new ApiError("INVALID_STATE", "Only invoices pending approval can be decided.");
    }
    const reason = request.reason.trim();
    if (reason.length < 5) {
      throw new ApiError("INVALID_REASON", "Enter a clear approval or rejection reason.");
    }

    const updated: Invoice = {
      ...invoice,
      status: request.decision,
      decisionReason: reason,
    };
    updated.audit = [
      ...invoice.audit,
      auditEntry(invoice, {
        action: request.decision === "APPROVED" ? "Invoice approved" : "Invoice rejected",
        actorName: user.name,
        actorRole: user.role,
        createdAt: workflowTimestamp(invoice),
        detail: reason,
      }),
    ];
    return replaceInvoice(updated);
  },
};
