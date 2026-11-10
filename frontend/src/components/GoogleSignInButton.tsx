import { useEffect, useRef } from "react";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (resp: { credential: string }) => void }) => void;
          renderButton: (parent: HTMLElement, options: { type: string; theme: string; size: string; width?: number; text?: string }) => void;
        };
      };
    };
  }
}

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

/** Renders Google's own "Sign in with Google" button via Google Identity
 * Services - no popup/redirect dance, just an ID token handed to our
 * callback, which the backend verifies (/api/auth/google). Silently
 * renders nothing if VITE_GOOGLE_CLIENT_ID isn't configured, so the rest of
 * the login/signup form still works without it. */
export default function GoogleSignInButton({ onCredential, text }: { onCredential: (credential: string) => void; text?: "signin_with" | "signup_with" }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!CLIENT_ID || !ref.current) return;

    let cancelled = false;
    function render() {
      if (cancelled || !window.google || !ref.current) return;
      window.google.accounts.id.initialize({
        client_id: CLIENT_ID!,
        callback: (resp) => onCredential(resp.credential),
      });
      window.google.accounts.id.renderButton(ref.current, { type: "standard", theme: "outline", size: "large", width: 320, text: text ?? "signin_with" });
    }

    if (window.google) {
      render();
    } else {
      // the GSI <script> tag in index.html loads async - poll briefly for it
      const id = setInterval(() => {
        if (window.google) {
          clearInterval(id);
          render();
        }
      }, 100);
      return () => {
        cancelled = true;
        clearInterval(id);
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!CLIENT_ID) return null;

  return (
    <div className="google-signin-wrap">
      <div className="auth-divider">
        <span>or</span>
      </div>
      <div ref={ref} />
    </div>
  );
}
