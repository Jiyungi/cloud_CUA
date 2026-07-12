export type DataMode = "mock" | "aws" | "invalid";

export interface RuntimeConfig {
  mode: DataMode;
  configuredMode: string;
  awsRegion: string;
  apiBaseUrl: string;
  cognitoUserPoolId: string;
  cognitoUserPoolClientId: string;
  cognitoDomain: string;
}

const REQUIRED_AWS_CONFIG: Array<keyof Omit<RuntimeConfig, "mode" | "configuredMode">> = [
  "awsRegion",
  "apiBaseUrl",
  "cognitoUserPoolId",
  "cognitoUserPoolClientId",
  "cognitoDomain",
];

export function resolveMode(value: string | undefined): DataMode {
  if (!value) {
    return "mock";
  }
  if (value === "mock" || value === "aws") {
    return value;
  }
  return "invalid";
}

const configuredMode = import.meta.env.VITE_DATA_MODE ?? "";

export const runtimeConfig: RuntimeConfig = {
  mode: resolveMode(configuredMode),
  configuredMode,
  awsRegion: import.meta.env.VITE_AWS_REGION ?? "",
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
  cognitoUserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID ?? "",
  cognitoUserPoolClientId: import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID ?? "",
  cognitoDomain: import.meta.env.VITE_COGNITO_DOMAIN ?? "",
};

export function missingAwsConfig(config: RuntimeConfig): string[] {
  if (config.mode !== "aws") {
    return [];
  }

  return REQUIRED_AWS_CONFIG.filter((key) => !config[key]).map((key) => key);
}
