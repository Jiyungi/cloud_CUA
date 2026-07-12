import { describe, expect, it } from "vitest";
import { describeDueDate, formatDateOnly } from "./dates";

describe("deterministic due-date warnings", () => {
  it("describes overdue, due-today, and upcoming invoices from the fixture date", () => {
    expect(describeDueDate("2026-07-10", "PENDING_APPROVAL")?.label).toBe("1 day overdue");
    expect(describeDueDate("2026-07-11", "PENDING_REVIEW")?.label).toBe("Due today");
    expect(describeDueDate("2026-07-17", "PENDING_REVIEW")?.label).toBe("Due in 6 days");
  });

  it("suppresses urgency for closed invoices and rejects invalid dates", () => {
    expect(describeDueDate("2026-07-10", "APPROVED")).toBeNull();
    expect(() => formatDateOnly("2026-02-31")).toThrow(/invalid calendar date/i);
  });
});
