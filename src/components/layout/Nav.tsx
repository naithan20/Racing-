import Link from "next/link";

const NAV_LINKS = [
  { href: "/races", label: "Races" },
  { href: "/value", label: "Value Scanner" },
  { href: "/lucky15", label: "Lucky 15" },
  { href: "/results", label: "Results" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/backtest", label: "Backtest Mode" },
  { href: "/import", label: "Import" },
  { href: "/data-quality", label: "Data Quality" },
  { href: "/data-explorer", label: "Dataset Explorer" },
];

export function Nav() {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg-elevated/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-8 px-4 sm:px-6">
        <Link href="/races" className="flex items-center gap-2 shrink-0">
          <span className="h-2 w-2 rounded-full bg-accent" />
          <span className="text-sm font-semibold tracking-wide text-text-primary">
            Racing<span className="text-accent">Edge</span>
          </span>
        </Link>
        <nav className="flex items-center gap-1 overflow-x-auto text-sm">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="whitespace-nowrap rounded-md px-3 py-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <span className="ml-auto hidden shrink-0 text-xs text-text-muted sm:block">
          Phase 2 — baseline model · synthetic data
        </span>
      </div>
    </header>
  );
}
