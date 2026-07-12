import { NavLink, Outlet } from "react-router-dom";
import { useAppState } from "../state/AppStateContext";

const NAV_ITEMS = [
  { to: "/invoices", label: "Invoice queue", shortLabel: "Queue" },
  { to: "/approvals", label: "Approvals", shortLabel: "Approvals" },
  { to: "/upload", label: "Upload invoice", shortLabel: "Upload" },
] as const;

export function AppShell(): React.JSX.Element {
  const { availableUsers, currentUser, switchUser } = useAppState();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/invoices" aria-label="InvoiceOps home">
          <span className="brand__mark" aria-hidden="true">
            IO
          </span>
          <span>
            InvoiceOps
            <small>Northstar Properties</small>
          </span>
        </NavLink>

        <nav className="side-nav" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `side-nav__item${isActive ? " side-nav__item--active" : ""}`}
            >
              <span className="side-nav__indicator" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <span className="environment-badge">DEMO DATA</span>
          <p>Frontend fixture · no AWS connection</p>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="topbar__tenant">Northstar Properties</span>
            <strong>Accounts payable workspace</strong>
          </div>
          <label className="role-switcher">
            Viewing as
            <select
              value={currentUser?.id ?? ""}
              onChange={(event) => void switchUser(event.target.value)}
              disabled={!currentUser}
            >
              {availableUsers.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name} · {user.role.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        </header>

        <main className="page-shell">
          <Outlet />
        </main>
      </div>

      <nav className="mobile-nav" aria-label="Mobile navigation">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `mobile-nav__item${isActive ? " mobile-nav__item--active" : ""}`}
          >
            {item.shortLabel}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
