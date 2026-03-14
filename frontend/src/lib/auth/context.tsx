/**
 * AuthContext — Always returns a dev user in M11.
 *
 * Scaffold for M13 Azure AD integration. Provides mock user context
 * so components can reference `useAuth()` now and get real auth later.
 *
 * In M13, this will be replaced with MSAL/Azure AD provider.
 */

"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import type { AuthContextValue, User } from "./types";

/** Mock dev user — always authenticated in M11 */
const DEV_USER: User = {
  id: "dev-user-001",
  name: "Dev Consultant",
  email: "dev@strategicgears.com",
  role: "consultant",
  avatarUrl: undefined,
  tenantId: undefined,
};

/** Default context value — authenticated dev user */
const defaultAuthValue: AuthContextValue = {
  user: DEV_USER,
  isLoading: false,
  isAuthenticated: true,
  error: null,
  signIn: async () => {
    // No-op in M11 — Azure AD redirect in M13
  },
  signOut: async () => {
    // No-op in M11 — Azure AD logout in M13
  },
};

const AuthContext = createContext<AuthContextValue>(defaultAuthValue);

export interface AuthProviderProps {
  children: ReactNode;
  /** Override user for testing */
  mockUser?: User | null;
}

/**
 * AuthProvider — Wraps app with auth context.
 *
 * In M11: always provides mock dev user.
 * In M13: will integrate with MSAL/Azure AD.
 */
export function AuthProvider({ children, mockUser }: AuthProviderProps) {
  const value = useMemo<AuthContextValue>(() => {
    // Allow test overrides
    if (mockUser !== undefined) {
      return {
        user: mockUser,
        isLoading: false,
        isAuthenticated: mockUser !== null,
        error: null,
        signIn: async () => {},
        signOut: async () => {},
      };
    }

    return defaultAuthValue;
  }, [mockUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * useAuth — Access current auth state and actions.
 *
 * Returns mock dev user in M11.
 */
export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
