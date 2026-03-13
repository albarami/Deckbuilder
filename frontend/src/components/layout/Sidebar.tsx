/**
 * Sidebar — Main navigation sidebar.
 *
 * Links: Dashboard, New Proposal, History.
 * Highlights the active route.
 * RTL-aware (mirrors in Arabic layout).
 */

"use client";

import { useTranslations } from "next-intl";
import { usePathname, Link } from "@/i18n/routing";

interface NavItem {
  href: string;
  labelKey: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  {
    href: "/",
    labelKey: "nav.dashboard",
    icon: <DashboardIcon />,
  },
  {
    href: "/new",
    labelKey: "nav.newProposal",
    icon: <NewProposalIcon />,
  },
  {
    href: "/history",
    labelKey: "nav.history",
    icon: <HistoryIcon />,
  },
];

export function Sidebar() {
  const t = useTranslations();
  const pathname = usePathname();

  return (
    <aside
      className="flex w-60 flex-col border-sg-border bg-sg-white ltr:border-r rtl:border-l"
      aria-label="Main navigation"
    >
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/" || pathname === ""
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sg-blue/10 text-sg-blue"
                  : "text-sg-slate hover:bg-sg-mist hover:text-sg-navy",
              ].join(" ")}
              aria-current={isActive ? "page" : undefined}
            >
              <span className="h-5 w-5 flex-shrink-0">{item.icon}</span>
              <span>{t(item.labelKey)}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom section — version info */}
      <div className="border-t border-sg-border p-3">
        <p className="text-xs text-sg-slate/50">DeckForge v0.1.0</p>
      </div>
    </aside>
  );
}

// ── Icons ──────────────────────────────────────────────────────────────

function DashboardIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className="h-5 w-5"
    >
      <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
    </svg>
  );
}

function NewProposalIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className="h-5 w-5"
    >
      <path
        fillRule="evenodd"
        d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className="h-5 w-5"
    >
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
        clipRule="evenodd"
      />
    </svg>
  );
}
