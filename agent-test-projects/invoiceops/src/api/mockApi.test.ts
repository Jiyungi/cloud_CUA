import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DecisionRequest, InvoiceLineItem, UploadRequest } from "../models";
import { mockApi, setMockUser } from "./mockApi";

const VALID_UPLOAD: UploadRequest = {
  fileName: "synthetic-invoice.pdf",
  fileType: "application/pdf",
  fileSize: 5_865,
  vendorId: "vendor-pacific-hvac",
  propertyId: "property-harbor-center",
};

const DECISIONS = [
  { decision: "APPROVED", reason: "Approved for the synthetic payment run." },
  { decision: "REJECTED", reason: "Reject until the work-order detail is corrected." },
] satisfies DecisionRequest[];

describe("InvoiceOps mock API", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("moves a vendor upload through deterministic extraction without a network call", async () => {
    setMockUser("user-vendor-rosa");

    const ticket = await mockApi.createUpload(VALID_UPLOAD);
    const invoice = await mockApi.getInvoice(ticket.invoiceId);

    expect(invoice.status).toBe("PENDING_REVIEW");
    expect(invoice.invoiceNumber).toBe("PH-1048");
    expect(invoice.audit.map((entry) => entry.action)).toEqual([
      "Invoice uploaded",
      "Extraction started",
      "Extraction completed",
    ]);
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });

  it("routes an unreadable synthetic file to manual review without fixture fields", async () => {
    setMockUser("user-vendor-rosa");

    const ticket = await mockApi.createUpload({ ...VALID_UPLOAD, fileName: "unreadable-invoice.pdf" });
    const invoice = await mockApi.getInvoice(ticket.invoiceId);

    expect(invoice).toMatchObject({
      status: "PENDING_REVIEW",
      invoiceNumber: "",
      invoiceDate: "",
      dueDate: "",
      workOrderNumber: "",
      extractionConfidence: 0,
      lineItems: [],
    });
    expect(invoice.audit.at(-1)?.action).toBe("Extraction needs manual review");
  });

  it("lets only AP correct fields, recomputes cents, and appends an audit entry", async () => {
    setMockUser("user-ap-daniel");
    const before = await mockApi.getInvoice("invoice-pacific-hvac-1048");
    const lineItems: InvoiceLineItem[] = before.lineItems.map((line, index) =>
      index === 0
        ? { ...line, unitPriceCents: line.unitPriceCents + 1, amountCents: 0 }
        : { ...line },
    );
    const subtotalCents = lineItems.reduce(
      (sum, line) => sum + line.quantity * line.unitPriceCents,
      0,
    );

    const updated = await mockApi.updateExtractedFields(before.id, {
      lineItems,
      subtotalCents,
      taxCents: before.taxCents,
      totalCents: subtotalCents + before.taxCents,
      reviewNote: "Verified work order and corrected compressor price by one cent.",
    });

    expect(updated.status).toBe("PENDING_APPROVAL");
    expect(updated.subtotalCents).toBe(1_180_001);
    expect(updated.totalCents).toBe(1_277_351);
    expect(updated.lineItems[0]?.amountCents).toBe(920_001);
    expect(updated.audit.slice(0, before.audit.length)).toEqual(before.audit);
    expect(updated.audit.at(-1)?.action).toBe("AP review completed");
  });

  it.each([
    ["vendor", "user-vendor-rosa"],
    ["finance administrator", "user-finance-morgan"],
  ])("rejects extracted-field changes from the %s role", async (_role, userId) => {
    setMockUser(userId);

    await expect(
      mockApi.updateExtractedFields("invoice-pacific-hvac-1048", {
        reviewNote: "Unauthorized update attempt.",
      }),
    ).rejects.toMatchObject({ code: "FORBIDDEN" });
  });

  it.each(DECISIONS)("records an assigned manager $decision decision append-only", async (request) => {
    setMockUser("user-manager-priya");
    const before = await mockApi.getInvoice("invoice-greenline-7781");

    const updated = await mockApi.decideInvoice(before.id, request);

    expect(updated.status).toBe(request.decision);
    expect(updated.decisionReason).toBe(request.reason);
    expect(updated.audit.slice(0, before.audit.length)).toEqual(before.audit);
    expect(updated.audit.at(-1)?.action).toBe(
      request.decision === "APPROVED" ? "Invoice approved" : "Invoice rejected",
    );
  });

  it.each([
    ["vendor", "user-vendor-rosa", "invoice-pacific-hvac-1048"],
    ["AP clerk", "user-ap-daniel", "invoice-greenline-7781"],
    ["finance administrator", "user-finance-morgan", "invoice-greenline-7781"],
  ])("rejects a decision from the %s role", async (_role, userId, invoiceId) => {
    setMockUser(userId);

    await expect(
      mockApi.decideInvoice(invoiceId, {
        decision: "APPROVED",
        reason: "Unauthorized synthetic decision.",
      }),
    ).rejects.toMatchObject({ code: "FORBIDDEN" });
  });

  it("does not expose another vendor's invoice", async () => {
    setMockUser("user-vendor-rosa");

    await expect(mockApi.getInvoice("invoice-greenline-7781")).rejects.toMatchObject({
      code: "NOT_FOUND",
    });
  });
});
