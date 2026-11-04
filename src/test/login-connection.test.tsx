import type { ComponentType, ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ApiError } from "@/features/api";

const session = vi.hoisted(() => ({
  login: vi.fn(),
  retry: vi.fn(),
  pending: false,
  waking: false,
  error: null as Error | null,
}));
vi.mock("@/lib/backend-session", () => ({
  useBackendSession: () => session,
  userHome: () => "/institution/dashboard",
}));
vi.mock("@/components/portal", () => ({
  PublicShell: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));
vi.mock("@/components/link", () => ({
  Link: ({ to, children }: { to: string; children: ReactNode }) => <a href={to}>{children}</a>,
  useGo: () => vi.fn(),
}));
import { Route } from "@/routes/login";
const Login = Route.options.component as ComponentType;

beforeEach(() => {
  session.pending = false;
  session.waking = false;
  session.error = null;
  vi.clearAllMocks();
});
afterEach(cleanup);

it("shows a waiting status and disables sign-in while session requests retry", () => {
  session.waking = true;
  render(<Login />);
  expect(screen.getByRole("status")).toHaveTextContent("Server is waking up");
  expect(screen.getByRole("button", { name: /Sign in to workspace/ })).toBeDisabled();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("shows the final connection error with a working retry action", () => {
  session.error = new ApiError(
    503,
    "The API could not be reached. Check the API server and try again.",
  );
  render(<Login />);
  expect(screen.getByRole("alert")).toHaveTextContent("The API could not be reached");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(session.retry).toHaveBeenCalledTimes(1);
});

it("hides an earlier error while a fresh connection check is running", () => {
  session.pending = true;
  session.error = new ApiError(503, "Earlier failure");
  render(<Login />);
  expect(screen.getByRole("status")).toHaveTextContent("Connecting to the server");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Sign in to workspace/ })).toBeDisabled();
});
