import { LayoutDashboard, MessageCircle, Settings, Users } from "lucide-react";
import { NavLink } from "react-router-dom";

const ITEMS = [
  { to: "/customers", label: "Customers", Icon: Users },
  { to: "/chat", label: "Assistant", Icon: MessageCircle },
  { to: "/dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { to: "/settings", label: "Settings", Icon: Settings },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      {ITEMS.map(({ to, label, Icon }) => (
        <NavLink key={to} to={to} className={({ isActive }) => `bottom-nav-item${isActive ? " active" : ""}`}>
          <span className="bottom-nav-icon" aria-hidden="true">
            <Icon size={20} strokeWidth={2} />
          </span>
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
