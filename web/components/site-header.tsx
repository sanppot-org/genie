import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="border-b border-border">
      <nav className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
        <Link href="/" className="font-semibold tracking-tight">
          Genie
        </Link>
        <Link
          href="/"
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          차트
        </Link>
        <Link
          href="/screening"
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          스크리닝
        </Link>
      </nav>
    </header>
  );
}
