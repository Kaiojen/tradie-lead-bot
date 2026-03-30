import Link from "next/link";

export function MarketingNav() {
  return (
    <header className="page-shell top-nav">
      <Link href="/" className="brand">
        Tradie Lead Bot
      </Link>
      <nav className="nav-links">
        <Link href="/pricing">Pricing</Link>
        <Link href="/login">Login</Link>
        <Link href="/login" className="button">
          Start free trial
        </Link>
      </nav>
    </header>
  );
}
