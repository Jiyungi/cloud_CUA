import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

vi.mock("./config/runtime", () => ({
  runtimeConfig: {
    mode: "aws",
    configuredMode: "aws",
    awsRegion: "us-east-1",
    apiBaseUrl: "",
    cognitoUserPoolId: "",
    cognitoUserPoolClientId: "",
    cognitoDomain: "",
  },
  missingAwsConfig: () => [
    "apiBaseUrl",
    "cognitoUserPoolId",
    "cognitoUserPoolClientId",
    "cognitoDomain",
  ],
}));

import { App } from "./App";

it("fails closed in AWS mode without claiming a connection or using demo data", () => {
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );

  expect(screen.getByRole("heading", { name: "AWS backend required" })).toBeInTheDocument();
  expect(screen.getByText("apiBaseUrl")).toBeInTheDocument();
  expect(screen.getByText("No AWS request was attempted.")).toBeInTheDocument();
  expect(screen.queryByText("DEMO DATA")).not.toBeInTheDocument();
  expect(screen.queryByText("AWS CONNECTED")).not.toBeInTheDocument();
  expect(vi.mocked(fetch)).not.toHaveBeenCalled();
});
