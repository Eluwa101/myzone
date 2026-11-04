import { NavLink } from "react-router-dom";

const ITEMS = [
  { to: "/customers", label: "Customers", icon: "👥" },
  { to: "/chat", label: "Assistant", icon: "💬" },
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      {ITEMS.map((item) => (
        <NavLink key={item.to} to={item.to} className={({ isActive }) => `bottom-nav-item${isActive ? " active" : ""}`}>
          <span className="bottom-nav-icon" aria-hidden="true">
            {item.icon}
          </span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
