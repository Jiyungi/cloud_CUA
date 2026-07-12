import { describe, expect, it } from "vitest";
import { centsToInput, parseDollarInput } from "./money";

describe("integer-cent input helpers", () => {
  it("round-trips exact cent values without floating-point arithmetic", () => {
    expect(centsToInput(1_277_350)).toBe("12773.50");
    expect(parseDollarInput("12773.50")).toBe(1_277_350);
    expect(parseDollarInput("0.01")).toBe(1);
  });

  it("rejects negative, over-precision, and unsafe values", () => {
    expect(parseDollarInput("-1.00")).toBeNull();
    expect(parseDollarInput("1.001")).toBeNull();
    expect(parseDollarInput("999999999999999.99")).toBeNull();
  });
});
