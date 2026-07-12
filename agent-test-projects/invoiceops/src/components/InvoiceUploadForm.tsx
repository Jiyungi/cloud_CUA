import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { FIXTURE_PROPERTIES, FIXTURE_VENDORS } from "../data/seed";
import { useAppState } from "../state/AppStateContext";
import { validateInvoiceFile } from "../utils/fileValidation";

type UploadProgress = "IDLE" | "UPLOADED" | "EXTRACTING";
type VendorId = (typeof FIXTURE_VENDORS)[number]["id"];
type PropertyId = (typeof FIXTURE_PROPERTIES)[number]["id"];

export function InvoiceUploadForm(): React.JSX.Element {
  const navigate = useNavigate();
  const { api, currentUser, refresh } = useAppState();
  const [file, setFile] = useState<File | null>(null);
  const [vendorId, setVendorId] = useState<VendorId>(FIXTURE_VENDORS[0].id);
  const [propertyId, setPropertyId] = useState<PropertyId>(FIXTURE_PROPERTIES[0].id);
  const [progress, setProgress] = useState<UploadProgress>("IDLE");
  const [error, setError] = useState<string | null>(null);

  const canUpload = currentUser?.role === "vendor";
  const vendorOptions =
    currentUser?.role === "vendor"
      ? FIXTURE_VENDORS.filter((vendor) => vendor.id === currentUser.vendorId)
      : FIXTURE_VENDORS;

  useEffect(() => {
    if (currentUser?.role === "vendor" && currentUser.vendorId) {
      setVendorId(currentUser.vendorId as VendorId);
    }
  }, [currentUser]);

  function handleFile(fileList: FileList | null): void {
    const selected = fileList?.[0] ?? null;
    setFile(selected);
    setProgress("IDLE");
    setError(selected ? validateInvoiceFile(selected) : null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!file) {
      setError("Choose a synthetic invoice file before continuing.");
      return;
    }
    const validationError = validateInvoiceFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (!canUpload) {
      setError("Only the vendor fixture role can upload invoices.");
      return;
    }

    try {
      setError(null);
      setProgress("UPLOADED");
      await Promise.resolve();
      setProgress("EXTRACTING");
      const ticket = await api.createUpload({
        fileName: file.name,
        fileType: file.type,
        fileSize: file.size,
        vendorId,
        propertyId,
      });
      await refresh();
      navigate(`/invoices/${ticket.invoiceId}`);
    } catch (cause) {
      setProgress("IDLE");
      setError(cause instanceof Error ? cause.message : "The mock extraction could not be completed.");
    }
  }

  if (!currentUser) {
    return <div className="empty-state">Loading the active fixture role…</div>;
  }

  if (!canUpload) {
    return (
      <div className="permission-state" role="note">
        <strong>Upload unavailable for this role</strong>
        <p>Switch to the vendor fixture user to submit an invoice.</p>
      </div>
    );
  }

  return (
    <form className="form-card" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <div className="upload-zone">
        <span className="upload-zone__icon" aria-hidden="true">
          ↑
        </span>
        <h2 id="invoice-file-title">Choose an invoice</h2>
        <p>PDF, JPG, PNG, or JPEG · maximum 10 MiB</p>
        <label className="button button--secondary" htmlFor="invoice-file">
          Browse files
          <input
            id="invoice-file"
            aria-describedby="invoice-file-selection"
            aria-label="Choose an invoice"
            type="file"
            accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png"
            onChange={(event) => handleFile(event.target.files)}
          />
        </label>
        <span id="invoice-file-selection" className="file-selection" aria-live="polite">
          {file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KiB` : "No file selected"}
        </span>
      </div>

      <div className="field-grid">
        <label>
          Vendor
          <select
            value={vendorId}
            onChange={(event) => setVendorId(event.target.value as VendorId)}
            disabled={currentUser.role === "vendor"}
          >
            {vendorOptions.map((vendor) => (
              <option key={vendor.id} value={vendor.id}>
                {vendor.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Property
          <select value={propertyId} onChange={(event) => setPropertyId(event.target.value as PropertyId)}>
            {FIXTURE_PROPERTIES.map((property) => (
              <option key={property.id} value={property.id}>
                {property.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="fixture-note">
        <strong>Need a safe document?</strong>
        <p>
          Use the clearly marked, two-page{" "}
          <a href="/test-fixtures/synthetic-invoice.pdf" download>
            synthetic invoice fixture
          </a>
          . It contains no real payment or vendor data. A synthetic file named with <code>unreadable</code> or{" "}
          <code>corrupt</code> exercises the manual-review failure path.
        </p>
      </div>

      {error ? (
        <div className="inline-error" role="alert">
          {error}
        </div>
      ) : null}
      {progress !== "IDLE" ? (
        <div className="workflow-progress" role="status" aria-live="polite">
          <strong>{progress === "UPLOADED" ? "Uploaded locally" : "Extracting deterministic fields"}</strong>
          <span>No document leaves this browser fixture.</span>
        </div>
      ) : null}

      <button className="button button--primary button--full" type="submit" disabled={progress !== "IDLE"}>
        {progress === "IDLE" ? "Extract invoice" : "Processing…"}
      </button>
    </form>
  );
}
