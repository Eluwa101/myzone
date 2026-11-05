import { Sparkles } from "lucide-react";

export default function AuthBrand() {
  return (
    <div className="auth-brand">
      <span className="auth-brand-mark" aria-hidden="true">
        <Sparkles size={18} strokeWidth={2.25} />
      </span>
      <h1>Mini CRM</h1>
    </div>
  );
}
