import type { InvoiceStatus } from "../models";
import { describeDueDate, FIXTURE_REFERENCE_DATE, formatDateOnly } from "../utils/dates";

interface DueDateFlagProps {
  dueDate: string;
  status: InvoiceStatus;
  referenceDate?: string;
}

export function DueDateFlag({
  dueDate,
  status,
  referenceDate = FIXTURE_REFERENCE_DATE,
}: DueDateFlagProps): React.JSX.Element {
  if (!dueDate) {
    return <span className="due-date-flag due-date-flag--missing">Due date not extracted</span>;
  }

  const description = describeDueDate(dueDate, status, referenceDate);
  const formattedDate = formatDateOnly(dueDate);

  return (
    <span className={`due-date-flag${description ? ` due-date-flag--${description.state}` : ""}`}>
      <time dateTime={dueDate} aria-label={`Due date ${formattedDate}`}>
        {formattedDate}
      </time>
      {description ? <span className="due-date-flag__label">{description.label}</span> : null}
    </span>
  );
}
