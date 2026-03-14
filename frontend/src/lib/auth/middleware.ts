/**
 * Auth middleware — Route protection scaffold.
 *
 * In M11: passes all requests (no real auth).
 * In M13: will validate Azure AD tokens and protect routes.
 *
 * This module exports helper functions that can be used in
 * Next.js middleware to check auth status before allowing access.
 */

// eslint-disable-next-line @typescript-eslint/no-unused-vars
import type { NextRequest } from "next/server";

/** Routes that require authentication (enforced in M13) */
export const PROTECTED_ROUTES = [
  "/pipeline",
  "/new",
  "/export",
  "/dashboard",
] as const;

/** Routes that are always public */
export const PUBLIC_ROUTES = [
  "/",
  "/login",
  "/health",
] as const;

/**
 * Check if a route requires authentication.
 *
 * In M11: always returns false (all routes accessible).
 * In M13: will check PROTECTED_ROUTES and validate session.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function isProtectedRoute(_pathname: string): boolean {
  // M11: no route protection — all routes accessible
  // M13: will check against PROTECTED_ROUTES
  return false;
}

/**
 * Check if request has valid auth session.
 *
 * In M11: always returns true (mock user always authenticated).
 * In M13: will validate Azure AD token from cookie/header.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function isAuthenticated(_request: NextRequest): boolean {
  // M11: always authenticated — mock user
  // M13: validate token from request cookies
  return true;
}

/**
 * Get the login redirect URL.
 *
 * In M11: returns null (no redirects needed).
 * In M13: will return Azure AD login URL with return_url parameter.
 */
export function getLoginRedirectUrl(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _request: NextRequest,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _locale: string,
): string | null {
  // M11: no redirects
  // M13: return `/${locale}/login?return_url=${encodeURIComponent(pathname)}`
  return null;
}
