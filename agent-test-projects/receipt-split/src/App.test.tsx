import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

function renderApp(route: string): ReturnType<typeof userEvent.setup> {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  );
  return user;
}

describe("ReceiptSplit mock application", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders seeded receipts with an explicit demo badge", async () => {
    renderApp("/receipts");

    expect(await screen.findByRole("heading", { name: "Harbor Table" })).toBeInTheDocument();
    expect(screen.getByText("DEMO DATA")).toBeInTheDocument();
  });

  it("uploads a supported receipt locally and never calls fetch", async () => {
    const user = renderApp("/upload");
    const file = new File(["synthetic receipt"], "summer-picnic.png", { type: "image/png" });

    await user.upload(await screen.findByLabelText(/choose a receipt/i), file);
    await user.click(screen.getByRole("button", { name: /review extracted receipt/i }));

    expect(await screen.findByRole("heading", { name: "Sunset Market" })).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("persists receipt corrections and moves to the split editor", async () => {
    const user = renderApp("/receipts/receipt-harbor-table/review");
    const merchant = await screen.findByLabelText("Merchant");

    await user.clear(merchant);
    await user.type(merchant, "Harbor Table Updated");
    await user.click(screen.getByRole("button", { name: /confirm and continue/i }));

    expect(await screen.findByRole("heading", { name: "Harbor Table Updated" })).toBeInTheDocument();
    await waitFor(() => expect(window.localStorage.getItem("receipt-split:mock-receipts:v1")).toContain("Harbor Table Updated"));
  });

  it("saves an exact equal split and records local reminder state", async () => {
    const user = renderApp("/receipts/receipt-harbor-table/split");

    await user.click(await screen.findByRole("button", { name: /split all equally/i }));
    await user.click(screen.getByRole("button", { name: /save exact split/i }));
    expect(await screen.findByText(/split saved locally/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /remind unpaid friends/i }));
    expect(await screen.findByText(/demo reminder scheduled locally/i)).toBeInTheDocument();
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });
});
