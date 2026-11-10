import { Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

export default function HeaderMenu() {
  return (
    <NavLink to="/settings" className={({ isActive }) => `icon-btn btn-ghost${isActive ? " header-icon-active" : ""}`} aria-label="Settings">
      <Settings size={19} />
    </NavLink>
  );
}
