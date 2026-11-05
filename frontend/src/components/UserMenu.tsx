import { LogOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";

function initialsFor(email: string): string {
  const local = email.split("@")[0] || "?";
  const parts = local.split(/[._-]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return local.slice(0, 2).toUpperCase();
}

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  if (!user) return null;

  return (
    <div className="user-menu" ref={ref}>
      <button className="avatar-btn" onClick={() => setOpen((o) => !o)} aria-label="Account menu">
        {initialsFor(user.email)}
      </button>
      {open && (
        <div className="user-menu-dropdown">
          <div className="user-menu-email">{user.email}</div>
          <div className="user-menu-role">{user.role}</div>
          <button className="btn-ghost user-menu-logout" onClick={logout}>
            <LogOut size={15} />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
