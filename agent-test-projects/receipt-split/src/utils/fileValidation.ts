const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "application/pdf"]);

export function validateReceiptFile(file: File): string | null {
  if (!ACCEPTED_TYPES.has(file.type)) {
    return "Choose a JPG, PNG, or PDF receipt.";
  }

  if (file.size === 0) {
    return "The selected file is empty.";
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "The receipt must be 10 MiB or smaller.";
  }

  return null;
}

export function validateUploadMetadata(fileType: string, fileSize: number): void {
  if (!ACCEPTED_TYPES.has(fileType)) {
    throw new Error("Unsupported receipt file type.");
  }
  if (fileSize <= 0 || fileSize > MAX_FILE_SIZE_BYTES) {
    throw new Error("Receipt file size is outside the allowed range.");
  }
}
