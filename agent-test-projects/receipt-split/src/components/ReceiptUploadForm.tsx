import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAppState } from "../state/AppStateContext";
import { validateReceiptFile } from "../utils/fileValidation";

export function ReceiptUploadForm(): React.JSX.Element {
  const navigate = useNavigate();
  const { api, refreshReceipts } = useAppState();
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>): void {
    const selected = event.target.files?.[0] ?? null;
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setFile(null);
    setError(null);

    if (!selected) {
      return;
    }

    const validationError = validateReceiptFile(selected);
    if (validationError) {
      setError(validationError);
      event.target.value = "";
      return;
    }

    setFile(selected);
    if (selected.type.startsWith("image/")) {
      setPreviewUrl(URL.createObjectURL(selected));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!file) {
      setError("Choose a receipt before continuing.");
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const ticket = await api.createUpload({
        fileName: file.name,
        fileType: file.type,
        fileSize: file.size,
      });
      await refreshReceipts();
      navigate(`/receipts/${ticket.receiptId}/review`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to prepare this receipt.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <form className="form-card" onSubmit={(event) => void handleSubmit(event)}>
      <div className="upload-zone">
        {previewUrl ? (
          <img className="upload-preview" src={previewUrl} alt="Preview of the selected receipt" />
        ) : (
          <span className="upload-zone__icon" aria-hidden="true">
            ↑
          </span>
        )}
        <h2 id="receipt-upload-title">{file ? file.name : "Choose a receipt"}</h2>
        <p>{file ? `${(file.size / 1024).toFixed(1)} KiB · stays in this browser` : "JPG, PNG, or PDF · maximum 10 MiB"}</p>
        <label className="button button--secondary" htmlFor="receipt-file">
          {file ? "Choose another file" : "Browse files"}
        </label>
        <input
          id="receipt-file"
          type="file"
          accept="image/jpeg,image/png,application/pdf"
          onChange={handleFileChange}
          aria-describedby="receipt-file-help"
        />
      </div>

      <div className="privacy-note" id="receipt-file-help">
        <strong>Demo-safe by design</strong>
        <p>In mock mode, selected files remain in this browser and are never uploaded.</p>
      </div>

      <a className="fixture-link" href="/test-fixtures/synthetic-receipt.png" download>
        Download the synthetic test receipt
      </a>

      {error ? <div className="error-state" role="alert">{error}</div> : null}

      <button className="button button--primary button--full" type="submit" disabled={!file || uploading}>
        {uploading ? "Extracting demo data…" : "Review extracted receipt"}
      </button>
    </form>
  );
}
