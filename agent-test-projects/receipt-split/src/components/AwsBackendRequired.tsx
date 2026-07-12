interface AwsBackendRequiredProps {
  missingConfig: string[];
  configurationError?: string;
}

export function AwsBackendRequired({
  missingConfig,
  configurationError,
}: AwsBackendRequiredProps): React.JSX.Element {
  return (
    <main className="blocking-page">
      <section className="blocking-card" aria-labelledby="backend-required-title">
        <span className="blocking-card__icon" aria-hidden="true">
          !
        </span>
        <p className="eyebrow">{configurationError ? "Runtime configuration blocked" : "AWS deployment fixture"}</p>
        <h1 id="backend-required-title">{configurationError ? "Invalid data mode" : "AWS backend required"}</h1>
        {configurationError ? (
          <p>{configurationError} ReceiptSplit will not fall back to demo data.</p>
        ) : (
          <p>
            ReceiptSplit is running in AWS mode, but this fixture intentionally contains no backend. Cloud CUA must
            provision and verify the services defined in <code>AGENT_TEST_SPEC.md</code>.
          </p>
        )}

        {configurationError ? null : missingConfig.length > 0 ? (
          <div className="blocking-card__details">
            <strong>Missing public configuration</strong>
            <ul>
              {missingConfig.map((key) => (
                <li key={key}>{key}</li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="blocking-card__details">
            <strong>Configuration present, adapter absent</strong>
            <p>The app will not claim a connection or fall back to demo data.</p>
          </div>
        )}

        <p className="blocking-card__note">No AWS request was attempted.</p>
      </section>
    </main>
  );
}
