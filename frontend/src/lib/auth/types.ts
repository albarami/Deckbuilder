/**
 * Auth types — User and Session shapes for M13 Azure AD compatibility.
 *
 * In M11, auth is scaffolded with mock data only.
 * These types define the contract that M13 will implement with real Azure AD.
 */

/** User profile from identity provider */
export interface User {
  /** Unique user ID (Azure AD OID in M13) */
  id: string;
  /** Display name */
  name: string;
  /** Email address */
  email: string;
  /** User role */
  role: UserRole;
  /** Profile image URL (optional) */
  avatarUrl?: string;
  /** Azure AD tenant (populated in M13) */
  tenantId?: string;
}

/** User roles for access control */
export type UserRole = "admin" | "consultant" | "reviewer" | "viewer";

/** Session state */
export interface AuthSession {
  /** Current user (null if not authenticated) */
  user: User | null;
  /** Whether the session is loading */
  isLoading: boolean;
  /** Whether the user is authenticated */
  isAuthenticated: boolean;
  /** Auth error message */
  error: string | null;
}

/** Auth context actions */
export interface AuthActions {
  /** Sign in (no-op in M11, Azure AD redirect in M13) */
  signIn: () => Promise<void>;
  /** Sign out (no-op in M11, Azure AD logout in M13) */
  signOut: () => Promise<void>;
}

/** Combined auth context value */
export type AuthContextValue = AuthSession & AuthActions;
