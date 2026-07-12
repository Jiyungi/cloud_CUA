export function UploadPage(): React.JSX.Element {
  return (
    <div className="page-stack page-stack--narrow">
      <header className="page-header">
        <p className="eyebrow">New receipt</p>
        <h1>Upload the bill</h1>
        <p>Use a clear photo or PDF. ReceiptSplit will show every extracted field for review before splitting.</p>
      </header>

      <section className="form-card" aria-labelledby="receipt-upload-title">
        <div className="upload-zone">
          <span className="upload-zone__icon" aria-hidden="true">
            ↑
          </span>
          <h2 id="receipt-upload-title">Choose a receipt</h2>
          <p>JPG, PNG, or PDF · maximum 10 MiB</p>
          <label className="button button--primary" htmlFor="receipt-file">
            Browse files
          </label>
          <input id="receipt-file" type="file" accept="image/jpeg,image/png,application/pdf" />
        </div>

        <div className="privacy-note">
          <strong>Demo-safe by design</strong>
          <p>In mock mode, selected files remain in this browser and are never uploaded.</p>
        </div>
      </section>
    </div>
  );
}
