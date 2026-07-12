import { describe, expect, it } from "vitest";
import { missingAwsConfig, resolveMode, type RuntimeConfig } from "./runtime";

describe("AWS runtime configuration", () => {
  it("does not require AWS values in explicit mock mode", () => {
    const config: RuntimeConfig = {
      mode: "mock",
      configuredMode: "mock",
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
      configuredMode: "aws",
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

  it("blocks every nonempty unsupported mode rather than falling back to mock", () => {
    expect(resolveMode("AWS")).toBe("invalid");
    expect(resolveMode("prod")).toBe("invalid");
    expect(resolveMode(" mock ")).toBe("invalid");
    expect(resolveMode(undefined)).toBe("mock");
  });
});
