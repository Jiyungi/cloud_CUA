import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AwsBackendRequired } from "./components/AwsBackendRequired";
import { missingAwsConfig, runtimeConfig } from "./config/runtime";
import { AppStateProvider } from "./state/AppStateContext";

const ReceiptsPage = lazy(async () => ({
  default: (await import("./pages/ReceiptsPage")).ReceiptsPage,
}));
const UploadPage = lazy(async () => ({
  default: (await import("./pages/UploadPage")).UploadPage,
}));
const ReviewPage = lazy(async () => ({
  default: (await import("./pages/ReviewPage")).ReviewPage,
}));
const SplitPage = lazy(async () => ({
  default: (await import("./pages/SplitPage")).SplitPage,
}));

export function App(): React.JSX.Element {
  if (runtimeConfig.mode === "aws") {
    return <AwsBackendRequired missingConfig={missingAwsConfig(runtimeConfig)} />;
  }

  return (
    <AppStateProvider>
      <Suspense fallback={<div className="route-loading">Loading ReceiptSplit…</div>}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate replace to="/receipts" />} />
            <Route path="receipts" element={<ReceiptsPage />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="receipts/:receiptId/review" element={<ReviewPage />} />
            <Route path="receipts/:receiptId/split" element={<SplitPage />} />
            <Route path="*" element={<Navigate replace to="/receipts" />} />
          </Route>
        </Routes>
      </Suspense>
    </AppStateProvider>
  );
}
