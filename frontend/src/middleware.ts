/**
 * Next.js Middleware — Locale detection + auth stub.
 *
 * Handles:
 * 1. Locale detection and URL rewriting (via next-intl)
 * 2. Auth route protection (scaffold — passes all in M11)
 *
 * In M13, step 2 will validate Azure AD tokens before allowing
 * access to protected routes.
 */

import { type NextRequest, NextResponse } from "next/server";
import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";
import { isProtectedRoute, isAuthenticated, getLoginRedirectUrl } from "./lib/auth/middleware";

// next-intl locale middleware
const intlMiddleware = createMiddleware(routing);

export default function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  // Extract locale from pathname (first segment after /)
  const localeMatch = pathname.match(/^\/(en|ar)\//);
  const locale = localeMatch?.[1] ?? "en";

  // Auth check (M11: always passes; M13: validates token)
  if (isProtectedRoute(pathname) && !isAuthenticated(request)) {
    const loginUrl = getLoginRedirectUrl(request, locale);
    if (loginUrl) {
      return NextResponse.redirect(new URL(loginUrl, request.url));
    }
  }

  // Delegate to next-intl for locale handling
  return intlMiddleware(request);
}

export const config = {
  // Match internationalized pathnames + root
  matcher: ["/", "/(en|ar)/:path*"],
};
