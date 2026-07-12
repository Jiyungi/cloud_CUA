import type { InvoiceStatus } from "../models";

export const FIXTURE_REFERENCE_DATE = "2026-07-11";

export type DueDateState = "overdue" | "due-today" | "due";

export interface DueDateDescription {
  state: DueDateState;
  label: string;
  daysUntilDue: number;
}

const CLOSED_STATUSES: ReadonlySet<InvoiceStatus> = new Set(["APPROVED", "REJECTED"]);
const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const DATE_FORMATTER = new Intl.DateTimeFormat("en-US", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
  year: "numeric",
});

function dateOnlyToEpochDay(value: string): number {
  const match = DATE_ONLY_PATTERN.exec(value);
  if (!match) {
    throw new RangeError(`Expected an ISO date in YYYY-MM-DD format, received "${value}".`);
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const timestamp = Date.UTC(year, month - 1, day);
  const parsed = new Date(timestamp);

  if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) {
    throw new RangeError(`Invalid calendar date "${value}".`);
  }

  return timestamp / 86_400_000;
}

export function formatDateOnly(value: string): string {
  return DATE_FORMATTER.format(new Date(dateOnlyToEpochDay(value) * 86_400_000));
}

export function describeDueDate(
  dueDate: string,
  status: InvoiceStatus,
  referenceDate = FIXTURE_REFERENCE_DATE,
): DueDateDescription | null {
  if (CLOSED_STATUSES.has(status)) {
    return null;
  }

  const daysUntilDue = dateOnlyToEpochDay(dueDate) - dateOnlyToEpochDay(referenceDate);

  if (daysUntilDue < 0) {
    const daysOverdue = Math.abs(daysUntilDue);
    return {
      state: "overdue",
      label: `${daysOverdue} ${daysOverdue === 1 ? "day" : "days"} overdue`,
      daysUntilDue,
    };
  }

  if (daysUntilDue === 0) {
    return { state: "due-today", label: "Due today", daysUntilDue };
  }

  return {
    state: "due",
    label: `Due in ${daysUntilDue} ${daysUntilDue === 1 ? "day" : "days"}`,
    daysUntilDue,
  };
}
