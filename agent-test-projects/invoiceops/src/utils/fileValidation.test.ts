import { describe, expect, it } from "vitest";
import { validateInvoiceFile, validateUploadMetadata } from "./fileValidation";

describe("invoice file validation", () => {
  it("accepts non-empty PDF, JPG, JPEG, and PNG files", () => {
    expect(validateInvoiceFile(new File(["pdf"], "invoice.pdf", { type: "application/pdf" }))).toBeNull();
    expect(validateInvoiceFile(new File(["jpg"], "invoice.jpg", { type: "image/jpeg" }))).toBeNull();
    expect(validateInvoiceFile(new File(["jpeg"], "invoice.jpeg", { type: "image/jpeg" }))).toBeNull();
    expect(validateInvoiceFile(new File(["png"], "invoice.png", { type: "image/png" }))).toBeNull();
  });

  it("rejects empty, unsupported, and oversized files", () => {
    expect(validateInvoiceFile(new File([], "empty.pdf", { type: "application/pdf" }))).toMatch(/empty/i);
    expect(validateInvoiceFile(new File(["text"], "invoice.txt", { type: "text/plain" }))).toMatch(/PDF/i);
    expect(() => validateUploadMetadata("application/pdf", 10 * 1024 * 1024 + 1)).toThrow(/size/i);
  });
});
