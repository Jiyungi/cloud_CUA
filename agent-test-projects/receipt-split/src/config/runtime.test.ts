import { describe, expect, it } from "vitest";
import { missingAwsConfig, type RuntimeConfig } from "./runtime";

describe("AWS runtime configuration", () => {
  it("does not require AWS values in mock mode", () => {
    const config: RuntimeConfig = {
      mode: "mock",
      awsRegion: "",
      apiBaseUrl: "",
      cognitoUserPoolId: "",
      cognitoUserPoolClientId: "",
      cognitoDomain: "",
    };

    expect(missingAwsConfig(config)).toEqual([]);
  });

  it("reports every missing public value in AWS mode", () => {
    const config: RuntimeConfig = {
      mode: "aws",
      awsRegion: "us-east-1",
      apiBaseUrl: "",
      cognitoUserPoolId: "",
      cognitoUserPoolClientId: "client-id",
      cognitoDomain: "",
    };

    expect(missingAwsConfig(config)).toEqual([
      "apiBaseUrl",
      "cognitoUserPoolId",
      "cognitoDomain",
    ]);
  });
});
