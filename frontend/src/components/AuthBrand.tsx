import Logo from "./Logo";

export default function AuthBrand() {
  return (
    <div className="auth-brand">
      <Logo size={40} className="auth-brand-logo" />
      <h1>MyShop</h1>
    </div>
  );
}
