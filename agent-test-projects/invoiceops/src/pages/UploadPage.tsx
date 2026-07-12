import { InvoiceUploadForm } from "../components/InvoiceUploadForm";

export function UploadPage(): React.JSX.Element {
  return (
    <div className="page-stack page-stack--narrow">
      <header className="page-header">
        <p className="eyebrow">Vendor intake</p>
        <h1>Upload an invoice</h1>
        <p>Use a synthetic PDF or image. No real financial, vendor, or property data belongs in this fixture.</p>
      </header>
      <InvoiceUploadForm />
    </div>
  );
}
