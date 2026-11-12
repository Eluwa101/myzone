import { ArrowLeftRight, LayoutDashboard, MessageCircle, Users } from "lucide-react";
import { NavLink } from "react-router-dom";
import Logo from "./Logo";

const ITEMS = [
  { to: "/customers", label: "Customers", Icon: Users },
  { to: "/chat", label: "Assistant", Icon: MessageCircle },
  { to: "/dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { to: "/data", label: "Data", Icon: ArrowLeftRight },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      <span className="nav-logo" aria-hidden="true">
        <Logo size={36} />
      </span>
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
