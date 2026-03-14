/**
 * AuthContext tests.
 *
 * Tests the auth scaffold providing mock dev user in M11.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthProvider, useAuth } from "./context";

// ── Helpers ────────────────────────────────────────────────────────────

function AuthDisplay() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="user-name">{auth.user?.name ?? "No user"}</span>
      <span data-testid="user-email">{auth.user?.email ?? "No email"}</span>
      <span data-testid="user-role">{auth.user?.role ?? "No role"}</span>
      <span data-testid="is-authenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="is-loading">{String(auth.isLoading)}</span>
    </div>
  );
}

// ── Tests ──────────────────────────────────────────────────────────────

describe("AuthContext", () => {
  it("provides mock dev user by default", () => {
    render(
      <AuthProvider>
        <AuthDisplay />
      </AuthProvider>,
    );
    expect(screen.getByTestId("user-name")).toHaveTextContent("Dev Consultant");
    expect(screen.getByTestId("user-email")).toHaveTextContent("dev@strategicgears.com");
    expect(screen.getByTestId("user-role")).toHaveTextContent("consultant");
    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("true");
    expect(screen.getByTestId("is-loading")).toHaveTextContent("false");
  });

  it("allows mock user override for testing", () => {
    render(
      <AuthProvider mockUser={{ id: "test-1", name: "Test User", email: "test@test.com", role: "admin" }}>
        <AuthDisplay />
      </AuthProvider>,
    );
    expect(screen.getByTestId("user-name")).toHaveTextContent("Test User");
    expect(screen.getByTestId("user-role")).toHaveTextContent("admin");
    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("true");
  });

  it("handles null mock user (not authenticated)", () => {
    render(
      <AuthProvider mockUser={null}>
        <AuthDisplay />
      </AuthProvider>,
    );
    expect(screen.getByTestId("user-name")).toHaveTextContent("No user");
    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("false");
  });

  it("works without provider (default context)", () => {
    render(<AuthDisplay />);
    expect(screen.getByTestId("user-name")).toHaveTextContent("Dev Consultant");
    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("true");
  });
});
