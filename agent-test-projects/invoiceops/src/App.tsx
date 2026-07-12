import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AwsBackendRequired } from "./components/AwsBackendRequired";
import { missingAwsConfig, runtimeConfig } from "./config/runtime";
import { AppStateProvider } from "./state/AppStateContext";

const InvoicesPage = lazy(async () => ({
  default: (await import("./pages/InvoicesPage")).InvoicesPage,
}));
const ApprovalsPage = lazy(async () => ({
  default: (await import("./pages/ApprovalsPage")).ApprovalsPage,
}));
const UploadPage = lazy(async () => ({
  default: (await import("./pages/UploadPage")).UploadPage,
}));
const InvoiceDetailPage = lazy(async () => ({
  default: (await import("./pages/InvoiceDetailPage")).InvoiceDetailPage,
}));

export function App(): React.JSX.Element {
  if (runtimeConfig.mode === "aws") {
    return <AwsBackendRequired missingConfig={missingAwsConfig(runtimeConfig)} />;
  }

  return (
    <AppStateProvider>
      <Suspense fallback={<div className="route-loading">Loading InvoiceOps…</div>}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate replace to="/invoices" />} />
            <Route path="invoices" element={<InvoicesPage />} />
            <Route path="invoices/:invoiceId" element={<InvoiceDetailPage />} />
            <Route path="approvals" element={<ApprovalsPage />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="*" element={<Navigate replace to="/invoices" />} />
          </Route>
        </Routes>
      </Suspense>
    </AppStateProvider>
  );
}
