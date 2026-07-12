interface MetricCardProps {
  label: string;
  value: string;
  detail: string;
  tone?: "default" | "warning" | "success";
}

export function MetricCard({ label, value, detail, tone = "default" }: MetricCardProps): React.JSX.Element {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}
