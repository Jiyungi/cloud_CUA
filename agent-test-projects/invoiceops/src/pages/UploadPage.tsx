export function UploadPage(): React.JSX.Element {
  return (
    <div className="page-stack page-stack--narrow">
      <header className="page-header">
        <p className="eyebrow">Vendor intake</p>
        <h1>Upload an invoice</h1>
        <p>Use a synthetic PDF or image. No real financial, vendor, or property data belongs in this fixture.</p>
      </header>

      <section className="form-card" aria-labelledby="invoice-file-title">
        <div className="upload-zone">
          <span className="upload-zone__icon" aria-hidden="true">
            ↑
          </span>
          <h2 id="invoice-file-title">Choose an invoice</h2>
          <p>PDF, JPG, PNG, or JPEG · maximum 10 MiB</p>
          <label className="button button--secondary" htmlFor="invoice-file">
            Browse files
          </label>
          <input id="invoice-file" aria-label="Choose an invoice" type="file" accept="application/pdf,image/jpeg,image/png" />
        </div>

        <div className="field-grid">
          <label>
            Vendor
            <select defaultValue="vendor-pacific-hvac">
              <option value="vendor-pacific-hvac">Pacific HVAC Services</option>
              <option value="vendor-greenline-electric">Greenline Electric</option>
            </select>
          </label>
          <label>
            Property
            <select defaultValue="property-harbor-center">
              <option value="property-harbor-center">Harbor Center</option>
              <option value="property-mission-square">Mission Square</option>
            </select>
          </label>
        </div>

        <div className="fixture-note">
          <strong>Mock-only shell</strong>
          <p>The complete local upload and extraction flow is added in the next fixture milestone.</p>
        </div>

        <button className="button button--primary button--full" type="button" disabled>
          Extract invoice
        </button>
      </section>
    </div>
  );
}
