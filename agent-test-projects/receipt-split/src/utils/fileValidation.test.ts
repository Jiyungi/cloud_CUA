import { describe, expect, it } from "vitest";
import { validateReceiptFile, validateUploadMetadata } from "./fileValidation";

describe("receipt file validation", () => {
  it("accepts non-empty JPG, PNG, and PDF files", () => {
    expect(validateReceiptFile(new File(["jpg"], "receipt.jpg", { type: "image/jpeg" }))).toBeNull();
    expect(validateReceiptFile(new File(["png"], "receipt.png", { type: "image/png" }))).toBeNull();
    expect(validateReceiptFile(new File(["pdf"], "receipt.pdf", { type: "application/pdf" }))).toBeNull();
  });

  it("rejects empty, unsupported, and oversized files", () => {
    expect(validateReceiptFile(new File([], "empty.png", { type: "image/png" }))).toMatch(/empty/i);
    expect(validateReceiptFile(new File(["text"], "receipt.txt", { type: "text/plain" }))).toMatch(/JPG/i);
    expect(() => validateUploadMetadata("image/png", 10 * 1024 * 1024 + 1)).toThrow(/size/i);
  });
});
