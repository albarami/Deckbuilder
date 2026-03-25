/**
 * Sidebar — Main navigation sidebar.
 *
 * Links: Dashboard, New Proposal, History.
 * Highlights the active route.
 * RTL-aware (mirrors in Arabic layout).
 */

"use client";

import { useEffect, useMemo, useState } from "react";
import { Clock3, GitBranch, Home, PlusCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { usePathname, Link } from "@/i18n/routing";
import { listSessions } from "@/lib/api/pipeline";
import { useIsPptEnabled } from "@/hooks/use-is-ppt-enabled";

interface NavItem {
  href: string;
  labelKey: string;
  icon: React.ReactNode;
}

export function Sidebar() {
  const t = useTranslations();
  const pathname = usePathname();
  const isPptEnabled = useIsPptEnabled();
  const [pipelineHref, setPipelineHref] = useState("/new");

  useEffect(() => {
    if (pathname.startsWith("/pipeline/")) {
      setPipelineHref(pathname);
      return;
    }

    let mounted = true;

    async function findLatestSession() {
      try {
        const response = await listSessions();
        if (!mounted) return;
        if (response.sessions.length > 0) {
          // sessions come sorted by most recent
          setPipelineHref(`/pipeline/${response.sessions[0].session_id}`);
          return;
        }
      } catch {
        // Backend unavailable — keep default /new
      }
    }

    void findLatestSession();
    return () => { mounted = false; };
  }, [pathname]);

  const navItems: (NavItem & { id: string })[] = useMemo(
    () => {
      const items: (NavItem & { id: string })[] = [
        {
          id: "dashboard",
          href: "/",
          labelKey: "nav.dashboard",
          icon: <Home className="h-4 w-4" aria-hidden="true" />,
        },
        {
          id: "new",
          href: "/new",
          labelKey: "nav.newProposal",
          icon: <PlusCircle className="h-4 w-4" aria-hidden="true" />,
        },
        {
          id: "pipeline",
          href: pipelineHref,
          labelKey: "pipeline.title",
          icon: <GitBranch className="h-4 w-4" aria-hidden="true" />,
        },
        {
          id: "history",
          href: "/history",
          labelKey: "nav.history",
          icon: <Clock3 className="h-4 w-4" aria-hidden="true" />,
        },
      ];

      if (isPptEnabled) {
        const pipelineBaseHref = extractPipelineBaseHref(pipelineHref);
        items.push({
          id: "slides",
          href: pipelineBaseHref ? `${pipelineBaseHref}/slides` : "/history",
          labelKey: "nav.slides",
          icon: <GitBranch className="h-4 w-4" aria-hidden="true" />,
        });
      }

      return items;
    },
    [isPptEnabled, pipelineHref],
  );

  return (
    <aside
      className="hidden w-60 flex-col border-sg-border bg-sg-white shadow-sg-card ltr:border-r rtl:border-l lg:flex"
      aria-label="Main navigation"
    >
      <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/" || pathname === ""
              : item.href.startsWith("/pipeline/")
                ? pathname.startsWith("/pipeline/")
                : pathname.startsWith(item.href);

          return (
            <Link
              key={item.id}
              href={item.href}
              className={[
                "sg-interactive flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-sg-blue/10 text-sg-blue shadow-sm"
                  : "text-sg-slate hover:bg-sg-mist hover:text-sg-navy",
              ].join(" ")}
              aria-current={isActive ? "page" : undefined}
            >
              <span className="h-5 w-5 flex-shrink-0 text-current">{item.icon}</span>
              <span>{t(item.labelKey)}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-sg-border p-3">
        <p className="text-[11px] font-medium text-sg-navy">Strategic Gears</p>
        <p className="text-[11px] text-sg-slate/55">DeckForge v0.1.0</p>
      </div>
    </aside>
  );
}

function extractPipelineBaseHref(path: string): string | null {
  const match = path.match(/^\/pipeline\/[^/]+/);
  return match ? match[0] : null;
}
