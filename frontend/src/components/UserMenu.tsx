import { Building2, LogOut, Undo2 } from "lucide-react";
import { leaveBusiness } from "../api/admin";
import AdminBusinessPicker from "./AdminBusinessPicker";
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
  const [picking, setPicking] = useState(false);
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
          <div className="user-menu-role">{user.admin_session ? "Admin session" : user.role}</div>
          {user.is_platform_admin && (
            <button
              className="btn-ghost user-menu-logout"
              onClick={() => {
                setOpen(false);
                setPicking(true);
              }}
            >
              <Building2 size={15} />
              Switch business (admin)
            </button>
          )}
          {user.admin_session && (
            <button className="btn-ghost user-menu-logout" onClick={() => leaveBusiness()}>
              <Undo2 size={15} />
              Back to my account
            </button>
          )}
          <button className="btn-ghost user-menu-logout" onClick={logout}>
            <LogOut size={15} />
            Log out
          </button>
        </div>
      )}
      {picking && <AdminBusinessPicker currentOrgId={user.org_id} onClose={() => setPicking(false)} />}
    </div>
  );
}
