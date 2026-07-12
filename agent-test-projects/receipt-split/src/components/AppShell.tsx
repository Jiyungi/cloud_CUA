import { Link, NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/receipts", label: "Receipts" },
  { to: "/upload", label: "Add receipt" },
] as const;

export function AppShell(): React.JSX.Element {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/receipts" aria-label="ReceiptSplit home">
          <span className="brand__mark" aria-hidden="true">
            R
          </span>
          <span>ReceiptSplit</span>
        </Link>

        <div className="topbar__actions">
          <span className="environment-badge">DEMO DATA</span>
          <div className="avatar" aria-label="Signed in as Jiyun">
            JK
          </div>
        </div>
      </header>

      <main className="page-shell">
        <Outlet />
      </main>

      <nav className="bottom-nav" aria-label="Primary navigation">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            className={({ isActive }) => `bottom-nav__item${isActive ? " bottom-nav__item--active" : ""}`}
            to={item.to}
          >
            <span className="bottom-nav__dot" aria-hidden="true" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
