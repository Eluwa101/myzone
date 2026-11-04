import { useAuth } from "../context/AuthContext";

export default function TopBar({ title }: { title: string }) {
  const { user, logout } = useAuth();
  return (
    <header className="top-bar">
      <h1>{title}</h1>
      {user && (
        <button className="btn-ghost" onClick={logout}>
          Log out
        </button>
      )}
    </header>
  );
}
