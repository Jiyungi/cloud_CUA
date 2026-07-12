import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const USER_KEY = "invoiceops:mock-user:v1";

function renderApp(
  route: string,
  userId?: string,
  applyAccept = true,
): ReturnType<typeof userEvent.setup> {
  if (userId) {
    window.localStorage.setItem(USER_KEY, userId);
  }
  const user = userEvent.setup({ applyAccept });
  render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  );
  return user;
}

describe("InvoiceOps mock application", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders the seeded queue with an explicit demo badge and filters", async () => {
    renderApp("/invoices");

    expect(await screen.findByRole("heading", { name: "Keep every invoice moving." })).toBeInTheDocument();
    expect(screen.getByText("DEMO DATA")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Invoice queue filters" })).toBeInTheDocument();
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });

  it("rejects an unsupported vendor upload before mock extraction", async () => {
    const user = renderApp("/upload", "user-vendor-rosa", false);
    const file = new File(["not an invoice"], "invoice.txt", { type: "text/plain" });

    await user.upload(await screen.findByLabelText(/choose an invoice/i), file);

    expect(screen.getByRole("alert")).toHaveTextContent(/PDF, JPG, JPEG, or PNG/i);
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });

  it("shows editable extracted fields only to the AP clerk", async () => {
    renderApp("/invoices/invoice-pacific-hvac-1048", "user-ap-daniel");

    expect(await screen.findByLabelText("Invoice number")).toHaveValue("PH-1048");
    expect(screen.getByRole("button", { name: /submit for property approval/i })).toBeEnabled();
  });

  it.each([
    ["vendor", "user-vendor-rosa"],
    ["finance administrator", "user-finance-morgan"],
  ])("keeps extracted fields read-only for the %s", async (_role, userId) => {
    renderApp("/invoices/invoice-pacific-hvac-1048", userId);

    expect(await screen.findByText(/AP clerk access is required/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit for property approval/i })).not.toBeInTheDocument();
  });

  it("shows decision controls only to the assigned property manager", async () => {
    renderApp("/invoices/invoice-greenline-7781", "user-manager-priya");

    expect(await screen.findByLabelText("Decision reason")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it.each([
    ["AP clerk", "user-ap-daniel"],
    ["finance administrator", "user-finance-morgan"],
  ])("hides decision controls from the %s", async (_role, userId) => {
    renderApp("/invoices/invoice-greenline-7781", userId);

    expect(await screen.findByText(/Only the assigned property manager/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });
});
