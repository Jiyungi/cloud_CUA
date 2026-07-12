export const MAX_INVOICE_FILE_SIZE_BYTES = 10 * 1024 * 1024;

const ACCEPTED_INVOICE_TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);
const ACCEPTED_INVOICE_EXTENSIONS = new Set(["pdf", "jpg", "jpeg", "png"]);
const FILE_TYPE_GUIDANCE = "Choose a PDF, JPG, JPEG, or PNG invoice.";

function isAcceptedInvoiceFile(file: File): boolean {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return ACCEPTED_INVOICE_TYPES.has(file.type.toLowerCase()) || ACCEPTED_INVOICE_EXTENSIONS.has(extension);
}

export function validateInvoiceFile(file: File): string | null {
  if (!isAcceptedInvoiceFile(file)) {
    return FILE_TYPE_GUIDANCE;
  }

  if (file.size === 0) {
    return "The selected invoice file is empty.";
  }

  if (file.size > MAX_INVOICE_FILE_SIZE_BYTES) {
    return "The invoice must be 10 MiB or smaller.";
  }

  return null;
}

export function validateUploadMetadata(fileType: string, fileSize: number): void {
  if (!ACCEPTED_INVOICE_TYPES.has(fileType)) {
    throw new Error("Unsupported invoice file type. Choose PDF, JPG, JPEG, or PNG.");
  }

  if (!Number.isFinite(fileSize) || fileSize <= 0 || fileSize > MAX_INVOICE_FILE_SIZE_BYTES) {
    throw new Error("Invoice file size must be greater than 0 bytes and no more than 10 MiB.");
  }
}
