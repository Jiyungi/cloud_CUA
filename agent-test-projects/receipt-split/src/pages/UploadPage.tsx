import { ReceiptUploadForm } from "../components/ReceiptUploadForm";

export function UploadPage(): React.JSX.Element {
  return (
    <div className="page-stack page-stack--narrow">
      <header className="page-header">
        <p className="eyebrow">New receipt</p>
        <h1>Upload the bill</h1>
        <p>Use a clear photo or PDF. ReceiptSplit will show every extracted field for review before splitting.</p>
      </header>

      <ReceiptUploadForm />
    </div>
  );
}
