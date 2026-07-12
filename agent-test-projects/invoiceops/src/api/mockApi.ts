import { SEEDED_INVOICES, SEEDED_USERS } from "../data/seed";
import type { AppUser, DecisionRequest, Invoice, InvoicePatch, UploadRequest, UploadTicket } from "../models";
import type { AppApi } from "./appApi";
import { ApiError } from "./appApi";

const INVOICES_KEY = "invoiceops:mock-invoices:v1";
const USER_KEY = "invoiceops:mock-user:v1";

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
    const invoiceId = `invoice-${request.fileName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    return {
      invoiceId,
      uploadUrl: `blob:mock-upload/${invoiceId}`,
      objectKey: `mock/${request.vendorId}/${request.propertyId}/${request.fileName}`,
    };
  },

  async updateExtractedFields(invoiceId, patch: InvoicePatch) {
    const user = activeUser();
    if (user.role !== "ap_clerk" && user.role !== "finance_admin") {
      throw new ApiError("FORBIDDEN", "Only AP or finance can correct extracted fields.");
    }
    const invoice = findVisibleInvoice(invoiceId);
    return replaceInvoice({ ...invoice, ...structuredClone(patch), status: "PENDING_APPROVAL" });
  },

  async decideInvoice(invoiceId, request: DecisionRequest) {
    const user = activeUser();
    const invoice = findVisibleInvoice(invoiceId);
    if (user.role !== "property_manager" || invoice.assignedManagerId !== user.id) {
      throw new ApiError("FORBIDDEN", "Only the assigned property manager can decide this invoice.");
    }
    return replaceInvoice({
      ...invoice,
      status: request.decision,
      decisionReason: request.reason,
    });
  },
};
